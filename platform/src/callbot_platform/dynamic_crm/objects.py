"""Custom object definitions and records."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.business_config.modules import SOURCE_ORG_CUSTOM
from callbot_platform.db.models.dynamic_crm import (
    OrganizationCustomObjectDefinition,
    OrganizationCustomObjectRecord,
)
from callbot_platform.dynamic_crm.config_cache import invalidate_effective_configuration
from callbot_platform.dynamic_crm.errors import DynamicCrmError
from callbot_platform.dynamic_crm.fields import (
    FieldDefinitionService,
    FieldValueService,
)
from callbot_platform.dynamic_crm.types import OWNER_SCOPE_OBJECT
from callbot_platform.dynamic_crm.validation import validate_object_key
from callbot_platform.telephony.audit import write_audit


class CustomObjectService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_definitions(
        self, tenant_id: UUID, *, include_archived: bool = False
    ) -> list[dict[str, Any]]:
        q = select(OrganizationCustomObjectDefinition).where(
            OrganizationCustomObjectDefinition.tenant_id == tenant_id
        )
        if not include_archived:
            q = q.where(OrganizationCustomObjectDefinition.archived_at.is_(None))
        rows = list(
            self._session.scalars(
                q.order_by(
                    OrganizationCustomObjectDefinition.display_order,
                    OrganizationCustomObjectDefinition.name,
                )
            ).all()
        )
        return [self._serialize_def(r) for r in rows]

    def create_definition(
        self,
        tenant_id: UUID,
        *,
        object_key: str,
        name: str,
        actor: str,
        plural_name: str | None = None,
        description: str = "",
        icon: str = "box",
        display_order: int = 100,
    ) -> dict[str, Any]:
        key = validate_object_key(object_key)
        existing = self._session.scalar(
            select(OrganizationCustomObjectDefinition).where(
                OrganizationCustomObjectDefinition.tenant_id == tenant_id,
                OrganizationCustomObjectDefinition.object_key == key,
            )
        )
        if existing is not None and existing.archived_at is None:
            raise DynamicCrmError("duplicate_object", f"Object already exists: {key}")
        if existing is not None:
            # Un-archive
            existing.archived_at = None
            existing.enabled = True
            existing.name = name.strip()[:128]
            existing.plural_name = (plural_name or f"{name}s").strip()[:128]
            existing.description = description or ""
            existing.icon = (icon or "box")[:64]
            existing.display_order = int(display_order)
            existing.updated_at = datetime.now(UTC)
            self._session.flush()
            row = existing
        else:
            row = OrganizationCustomObjectDefinition(
                tenant_id=tenant_id,
                object_key=key,
                name=name.strip()[:128],
                plural_name=(plural_name or f"{name.strip()}s")[:128],
                description=description or "",
                icon=(icon or "box")[:64],
                enabled=True,
                display_order=int(display_order),
                source=SOURCE_ORG_CUSTOM,
            )
            self._session.add(row)
            self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_custom_object_created",
            resource_ids={"object_id": str(row.id), "object_key": key},
        )
        invalidate_effective_configuration(tenant_id)
        return self._serialize_def(row)

    def update_definition(
        self, tenant_id: UUID, object_id: UUID, *, actor: str, **fields: Any
    ) -> dict[str, Any]:
        row = self._get_def(tenant_id, object_id)
        if "name" in fields and fields["name"] is not None:
            row.name = str(fields["name"]).strip()[:128]
        if "plural_name" in fields and fields["plural_name"] is not None:
            row.plural_name = str(fields["plural_name"]).strip()[:128]
        if "description" in fields and fields["description"] is not None:
            row.description = str(fields["description"])
        if "icon" in fields and fields["icon"] is not None:
            row.icon = str(fields["icon"])[:64]
        if "enabled" in fields and fields["enabled"] is not None:
            row.enabled = bool(fields["enabled"])
        if "display_order" in fields and fields["display_order"] is not None:
            row.display_order = int(fields["display_order"])
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_custom_object_updated",
            resource_ids={"object_id": str(row.id)},
        )
        invalidate_effective_configuration(tenant_id)
        return self._serialize_def(row)

    def archive_definition(
        self, tenant_id: UUID, object_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._get_def(tenant_id, object_id)
        # Soft-delete definition; do not cascade-delete records.
        row.enabled = False
        row.archived_at = datetime.now(UTC)
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_custom_object_archived",
            resource_ids={"object_id": str(row.id)},
        )
        invalidate_effective_configuration(tenant_id)
        return self._serialize_def(row)

    def create_record(
        self,
        tenant_id: UUID,
        object_id: UUID,
        *,
        actor: str,
        values: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        definition = self._get_def(tenant_id, object_id)
        if not definition.enabled or definition.archived_at is not None:
            raise DynamicCrmError("object_disabled", "Custom object is not available")
        record = OrganizationCustomObjectRecord(
            tenant_id=tenant_id,
            object_definition_id=definition.id,
            created_by=actor,
            updated_by=actor,
        )
        self._session.add(record)
        self._session.flush()
        FieldValueService(self._session).set_values(
            tenant_id,
            record_type="object",
            record_id=record.id,
            owner_scope=OWNER_SCOPE_OBJECT,
            owner_key=definition.object_key,
            values=values or {},
            apply_defaults=True,
            is_create=True,
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_custom_object_record_created",
            resource_ids={
                "object_id": str(definition.id),
                "record_id": str(record.id),
            },
        )
        return self.get_record(tenant_id, object_id, record.id)

    def update_record(
        self,
        tenant_id: UUID,
        object_id: UUID,
        record_id: UUID,
        *,
        actor: str,
        values: dict[str, Any],
    ) -> dict[str, Any]:
        definition = self._get_def(tenant_id, object_id)
        record = self._get_record(tenant_id, definition.id, record_id)
        if record.archived_at is not None:
            raise DynamicCrmError("record_archived", "Record is archived")
        FieldValueService(self._session).set_values(
            tenant_id,
            record_type="object",
            record_id=record.id,
            owner_scope=OWNER_SCOPE_OBJECT,
            owner_key=definition.object_key,
            values=values,
            apply_defaults=False,
            is_create=False,
        )
        record.updated_by = actor
        record.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_custom_object_record_updated",
            resource_ids={
                "object_id": str(definition.id),
                "record_id": str(record.id),
            },
            payload_summary={"fields": sorted(values.keys())},
        )
        return self.get_record(tenant_id, object_id, record_id)

    def archive_record(
        self, tenant_id: UUID, object_id: UUID, record_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        definition = self._get_def(tenant_id, object_id)
        record = self._get_record(tenant_id, definition.id, record_id)
        record.archived_at = datetime.now(UTC)
        record.updated_by = actor
        record.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_custom_object_record_archived",
            resource_ids={"record_id": str(record.id)},
        )
        return self.get_record(tenant_id, object_id, record_id)

    def get_record(
        self, tenant_id: UUID, object_id: UUID, record_id: UUID
    ) -> dict[str, Any]:
        definition = self._get_def(tenant_id, object_id)
        record = self._get_record(tenant_id, definition.id, record_id)
        values = FieldValueService(self._session).get_values(
            tenant_id, record_type="object", record_id=record.id
        )
        return {
            "id": str(record.id),
            "object_definition_id": str(definition.id),
            "object_key": definition.object_key,
            "values": values,
            "created_by": record.created_by,
            "updated_by": record.updated_by,
            "created_at": record.created_at.isoformat() if record.created_at else None,
            "updated_at": record.updated_at.isoformat() if record.updated_at else None,
            "archived_at": record.archived_at.isoformat()
            if record.archived_at
            else None,
        }

    def list_records(
        self,
        tenant_id: UUID,
        object_id: UUID,
        *,
        include_archived: bool = False,
        limit: int = 50,
        offset: int = 0,
        filters: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        definition = self._get_def(tenant_id, object_id)
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        q = select(OrganizationCustomObjectRecord).where(
            OrganizationCustomObjectRecord.tenant_id == tenant_id,
            OrganizationCustomObjectRecord.object_definition_id == definition.id,
        )
        if not include_archived:
            q = q.where(OrganizationCustomObjectRecord.archived_at.is_(None))
        if filters:
            # Cap filter ID fetch to page window + offset (max 200) — no silent 1000 truncation.
            fetch_limit = min(200, offset + limit)
            ids = FieldValueService(self._session).find_record_ids(
                tenant_id,
                owner_scope=OWNER_SCOPE_OBJECT,
                owner_key=definition.object_key,
                filters=filters,
                limit=max(fetch_limit, limit),
            )
            q = q.where(OrganizationCustomObjectRecord.id.in_(ids or [UUID(int=0)]))
        total = (
            self._session.scalar(select(func.count()).select_from(q.subquery())) or 0
        )
        rows = list(
            self._session.scalars(
                q.order_by(OrganizationCustomObjectRecord.created_at.desc())
                .offset(offset)
                .limit(limit)
            ).all()
        )
        items = [self.get_record(tenant_id, object_id, r.id) for r in rows]
        fields = FieldDefinitionService(self._session).list_fields(
            tenant_id,
            owner_scope=OWNER_SCOPE_OBJECT,
            owner_key=definition.object_key,
        )
        return {
            "object": self._serialize_def(definition),
            "fields": fields,
            "items": items,
            "total": int(total),
            "limit": limit,
            "offset": offset,
        }

    def _get_def(
        self, tenant_id: UUID, object_id: UUID
    ) -> OrganizationCustomObjectDefinition:
        row = self._session.scalar(
            select(OrganizationCustomObjectDefinition).where(
                OrganizationCustomObjectDefinition.tenant_id == tenant_id,
                OrganizationCustomObjectDefinition.id == object_id,
            )
        )
        if row is None:
            raise DynamicCrmError("not_found", "Custom object not found")
        return row

    def _get_record(
        self, tenant_id: UUID, object_definition_id: UUID, record_id: UUID
    ) -> OrganizationCustomObjectRecord:
        row = self._session.scalar(
            select(OrganizationCustomObjectRecord).where(
                OrganizationCustomObjectRecord.tenant_id == tenant_id,
                OrganizationCustomObjectRecord.object_definition_id
                == object_definition_id,
                OrganizationCustomObjectRecord.id == record_id,
            )
        )
        if row is None:
            raise DynamicCrmError("not_found", "Record not found")
        return row

    def _serialize_def(self, row: OrganizationCustomObjectDefinition) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "object_key": row.object_key,
            "name": row.name,
            "plural_name": row.plural_name,
            "description": row.description,
            "icon": row.icon,
            "enabled": row.enabled,
            "display_order": row.display_order,
            "source": row.source,
            "archived_at": row.archived_at.isoformat() if row.archived_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
