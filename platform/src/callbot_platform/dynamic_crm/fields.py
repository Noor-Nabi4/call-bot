"""Custom field definition and value services."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.business_config.modules import MODULE_KEYS, SOURCE_ORG_CUSTOM
from callbot_platform.db.models.crm_config import OrganizationCrmField
from callbot_platform.db.models.dynamic_crm import CrmCustomFieldValue
from callbot_platform.dynamic_crm.config_cache import invalidate_effective_configuration
from callbot_platform.dynamic_crm.errors import DynamicCrmError
from callbot_platform.dynamic_crm.types import (
    OWNER_SCOPE_MODULE,
    OWNER_SCOPE_OBJECT,
    normalize_field_type,
)
from callbot_platform.dynamic_crm.validation import (
    unpack_value,
    validate_and_pack_value,
    validate_field_key,
)
from callbot_platform.telephony.audit import write_audit


class FieldDefinitionService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_fields(
        self,
        tenant_id: UUID,
        *,
        owner_scope: str,
        owner_key: str,
        include_disabled: bool = False,
    ) -> list[dict[str, Any]]:
        q = select(OrganizationCrmField).where(
            OrganizationCrmField.tenant_id == tenant_id,
            OrganizationCrmField.owner_scope == owner_scope,
            OrganizationCrmField.owner_key == owner_key,
        )
        if not include_disabled:
            q = q.where(OrganizationCrmField.enabled.is_(True))
        rows = list(
            self._session.scalars(
                q.order_by(
                    OrganizationCrmField.display_order,
                    OrganizationCrmField.field_key,
                )
            ).all()
        )
        return [self._serialize(r) for r in rows]

    def create_field(
        self,
        tenant_id: UUID,
        *,
        owner_scope: str,
        owner_key: str,
        field_key: str,
        label: str,
        field_type: str,
        actor: str,
        description: str = "",
        required: bool = False,
        enabled: bool = True,
        display_order: int = 100,
        default_value: Any = None,
        configuration: dict[str, Any] | None = None,
        validation_rules: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        scope = owner_scope.strip().lower()
        key_owner = owner_key.strip()
        if scope == OWNER_SCOPE_MODULE:
            key_owner = key_owner.upper()
            if key_owner not in MODULE_KEYS:
                raise DynamicCrmError("unknown_module", f"Unknown module: {owner_key}")
        elif scope != OWNER_SCOPE_OBJECT:
            raise DynamicCrmError(
                "invalid_owner_scope", "owner_scope must be module|object"
            )

        fkey = validate_field_key(field_key)
        ftype = normalize_field_type(field_type)
        existing = self._session.scalar(
            select(OrganizationCrmField).where(
                OrganizationCrmField.tenant_id == tenant_id,
                OrganizationCrmField.owner_scope == scope,
                OrganizationCrmField.owner_key == key_owner,
                OrganizationCrmField.field_key == fkey,
            )
        )
        if existing is not None:
            raise DynamicCrmError("duplicate_field", f"Field already exists: {fkey}")

        if default_value is not None:
            validate_and_pack_value(
                ftype,
                default_value,
                configuration=configuration or {},
                validation_rules=validation_rules or {},
            )

        row = OrganizationCrmField(
            tenant_id=tenant_id,
            module_key=key_owner if scope == OWNER_SCOPE_MODULE else None,
            owner_scope=scope,
            owner_key=key_owner,
            field_key=fkey,
            label=(label or fkey).strip()[:128],
            description=(description or "")[:512],
            field_type=ftype,
            required=bool(required),
            enabled=bool(enabled),
            display_order=int(display_order),
            default_value=default_value,
            configuration=dict(configuration or {}),
            validation_rules=dict(validation_rules or {}),
            source=SOURCE_ORG_CUSTOM,
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_field_created",
            resource_ids={"field_id": str(row.id), "field_key": fkey},
            payload_summary={
                "owner_scope": scope,
                "owner_key": key_owner,
                "type": ftype,
            },
        )
        invalidate_effective_configuration(tenant_id)
        return self._serialize(row)

    def update_field(
        self,
        tenant_id: UUID,
        field_id: UUID,
        *,
        actor: str,
        **fields: Any,
    ) -> dict[str, Any]:
        row = self._get(tenant_id, field_id)
        before = self._serialize(row)
        if "label" in fields and fields["label"] is not None:
            row.label = str(fields["label"]).strip()[:128]
        if "description" in fields and fields["description"] is not None:
            row.description = str(fields["description"])[:512]
        if "required" in fields and fields["required"] is not None:
            row.required = bool(fields["required"])
        if "enabled" in fields and fields["enabled"] is not None:
            row.enabled = bool(fields["enabled"])
        if "display_order" in fields and fields["display_order"] is not None:
            row.display_order = int(fields["display_order"])
        if "configuration" in fields and fields["configuration"] is not None:
            row.configuration = dict(fields["configuration"])
        if "validation_rules" in fields and fields["validation_rules"] is not None:
            row.validation_rules = dict(fields["validation_rules"])
        if "default_value" in fields:
            if fields["default_value"] is not None:
                validate_and_pack_value(
                    row.field_type,
                    fields["default_value"],
                    configuration=row.configuration or {},
                    validation_rules=row.validation_rules or {},
                )
            row.default_value = fields["default_value"]
        # field_type changes are intentionally not supported (destructive).
        row.source = SOURCE_ORG_CUSTOM
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_field_updated",
            resource_ids={"field_id": str(row.id)},
            payload_summary={"before": before, "after": self._serialize(row)},
        )
        invalidate_effective_configuration(tenant_id)
        return self._serialize(row)

    def require_field_for_owner(
        self,
        tenant_id: UUID,
        field_id: UUID,
        *,
        owner_scope: str,
        owner_key: str,
    ) -> OrganizationCrmField:
        row = self._get(tenant_id, field_id)
        expected_scope = owner_scope.strip().lower()
        expected_key = (
            owner_key.strip().upper()
            if expected_scope == OWNER_SCOPE_MODULE
            else owner_key.strip().lower()
        )
        if row.owner_scope != expected_scope or row.owner_key != expected_key:
            raise DynamicCrmError("not_found", "Field not found")
        return row

    def disable_field(
        self, tenant_id: UUID, field_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        return self.update_field(tenant_id, field_id, actor=actor, enabled=False)

    def _get(self, tenant_id: UUID, field_id: UUID) -> OrganizationCrmField:
        row = self._session.scalar(
            select(OrganizationCrmField).where(
                OrganizationCrmField.tenant_id == tenant_id,
                OrganizationCrmField.id == field_id,
            )
        )
        if row is None:
            raise DynamicCrmError("not_found", "Field not found")
        return row

    def _serialize(self, row: OrganizationCrmField) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "owner_scope": row.owner_scope,
            "owner_key": row.owner_key,
            "module_key": row.module_key,
            "field_key": row.field_key,
            "label": row.label,
            "description": row.description,
            "field_type": row.field_type,
            "required": row.required,
            "enabled": row.enabled,
            "display_order": row.display_order,
            "default_value": row.default_value,
            "configuration": dict(row.configuration or {}),
            "validation_rules": dict(row.validation_rules or {}),
            "source": row.source,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }


class FieldValueService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def set_values(
        self,
        tenant_id: UUID,
        *,
        record_type: str,
        record_id: UUID,
        owner_scope: str,
        owner_key: str,
        values: dict[str, Any],
        apply_defaults: bool = False,
        is_create: bool = False,
    ) -> dict[str, Any]:
        defs = list(
            self._session.scalars(
                select(OrganizationCrmField).where(
                    OrganizationCrmField.tenant_id == tenant_id,
                    OrganizationCrmField.owner_scope == owner_scope,
                    OrganizationCrmField.owner_key == owner_key,
                    OrganizationCrmField.enabled.is_(True),
                )
            ).all()
        )
        by_key = {d.field_key: d for d in defs}
        merged = dict(values)
        if apply_defaults:
            for d in defs:
                if d.field_key not in merged and d.default_value is not None:
                    merged[d.field_key] = d.default_value

        if is_create:
            for d in defs:
                if d.required and (
                    d.field_key not in merged
                    or merged[d.field_key] is None
                    or merged[d.field_key] == ""
                ):
                    raise DynamicCrmError(
                        "required",
                        f"Required field missing: {d.field_key}",
                    )

        for key, raw in merged.items():
            definition = by_key.get(key)
            if definition is None:
                raise DynamicCrmError(
                    "unknown_field", f"Unknown or disabled field: {key}"
                )
            packed = validate_and_pack_value(
                definition.field_type,
                raw,
                configuration=definition.configuration or {},
                validation_rules=definition.validation_rules or {},
                required=bool(definition.required) and is_create,
            )
            row = self._session.scalar(
                select(CrmCustomFieldValue).where(
                    CrmCustomFieldValue.tenant_id == tenant_id,
                    CrmCustomFieldValue.field_definition_id == definition.id,
                    CrmCustomFieldValue.record_id == record_id,
                )
            )
            if row is None:
                row = CrmCustomFieldValue(
                    tenant_id=tenant_id,
                    field_definition_id=definition.id,
                    record_type=record_type,
                    record_id=record_id,
                )
                self._session.add(row)
            for col, val in packed.items():
                setattr(row, col, val)
            row.updated_at = datetime.now(UTC)
        self._session.flush()
        return self.get_values(tenant_id, record_type=record_type, record_id=record_id)

    def get_values(
        self, tenant_id: UUID, *, record_type: str, record_id: UUID
    ) -> dict[str, Any]:
        rows = list(
            self._session.scalars(
                select(CrmCustomFieldValue).where(
                    CrmCustomFieldValue.tenant_id == tenant_id,
                    CrmCustomFieldValue.record_type == record_type,
                    CrmCustomFieldValue.record_id == record_id,
                )
            ).all()
        )
        if not rows:
            return {}
        field_ids = {r.field_definition_id for r in rows}
        defs = {
            d.id: d
            for d in self._session.scalars(
                select(OrganizationCrmField).where(
                    OrganizationCrmField.tenant_id == tenant_id,
                    OrganizationCrmField.id.in_(field_ids),
                )
            ).all()
        }
        out: dict[str, Any] = {}
        for row in rows:
            definition = defs.get(row.field_definition_id)
            if definition is None:
                continue
            out[definition.field_key] = unpack_value(definition.field_type, row)
        return out

    def find_record_ids(
        self,
        tenant_id: UUID,
        *,
        owner_scope: str,
        owner_key: str,
        filters: list[dict[str, Any]],
        limit: int = 50,
    ) -> list[UUID]:
        """Controlled custom-field filter → record IDs (parameterized SQL)."""
        from callbot_platform.dynamic_crm.query import apply_field_filters

        return apply_field_filters(
            self._session,
            tenant_id,
            owner_scope=owner_scope,
            owner_key=owner_key,
            filters=filters,
            limit=limit,
        )
