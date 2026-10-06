"""CRM relationship definitions and instances."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.business_config.modules import MODULE_KEYS
from callbot_platform.db.models.catalog import Product
from callbot_platform.db.models.crm import Call, Customer, Lead
from callbot_platform.db.models.dynamic_crm import (
    OrganizationCrmRelationshipDefinition,
    OrganizationCrmRelationshipLink,
    OrganizationCustomObjectDefinition,
    OrganizationCustomObjectRecord,
)
from callbot_platform.db.models.jobs import Job, Technician
from callbot_platform.db.models.scheduling import Appointment
from callbot_platform.dynamic_crm.config_cache import invalidate_effective_configuration
from callbot_platform.dynamic_crm.entity_kinds import (
    ENTITY_KIND_CONFIGURATION_ONLY,
    classify_module_entity,
    relationship_record_supported,
)
from callbot_platform.dynamic_crm.errors import DynamicCrmError
from callbot_platform.dynamic_crm.types import (
    CARDINALITY_MANY_TO_MANY,
    CARDINALITY_ONE_TO_MANY,
    CARDINALITY_ONE_TO_ONE,
    OWNER_SCOPE_MODULE,
    OWNER_SCOPE_OBJECT,
    normalize_cardinality,
)
from callbot_platform.dynamic_crm.validation import validate_relationship_key
from callbot_platform.telephony.audit import write_audit


class RelationshipService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_definitions(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = list(
            self._session.scalars(
                select(OrganizationCrmRelationshipDefinition)
                .where(OrganizationCrmRelationshipDefinition.tenant_id == tenant_id)
                .order_by(OrganizationCrmRelationshipDefinition.relationship_key)
            ).all()
        )
        return [self._serialize_def(r) for r in rows]

    def create_definition(
        self,
        tenant_id: UUID,
        *,
        relationship_key: str,
        source_type: str,
        source_key: str,
        target_type: str,
        target_key: str,
        cardinality: str,
        actor: str,
        label: str = "",
        inverse_label: str = "",
        required: bool = False,
    ) -> dict[str, Any]:
        key = validate_relationship_key(relationship_key)
        src_type = source_type.strip().lower()
        tgt_type = target_type.strip().lower()
        src_key = self._normalize_entity_key(src_type, source_key)
        tgt_key = self._normalize_entity_key(tgt_type, target_key)
        card = normalize_cardinality(cardinality)
        self._assert_entity_exists(tenant_id, src_type, src_key)
        self._assert_entity_exists(tenant_id, tgt_type, tgt_key)
        # Reject definitions that target configuration-only modules (no record table).
        if not relationship_record_supported(
            entity_type=src_type, entity_key=src_key
        ) or not relationship_record_supported(
            entity_type=tgt_type, entity_key=tgt_key
        ):
            raise DynamicCrmError(
                "entity_not_materialized",
                "Relationships require PLATFORM_ENTITY or CUSTOM_OBJECT targets; "
                "configuration-only modules cannot participate in record links yet",
            )

        existing = self._session.scalar(
            select(OrganizationCrmRelationshipDefinition).where(
                OrganizationCrmRelationshipDefinition.tenant_id == tenant_id,
                OrganizationCrmRelationshipDefinition.relationship_key == key,
            )
        )
        if existing is not None:
            raise DynamicCrmError(
                "duplicate_relationship", f"Relationship already exists: {key}"
            )

        row = OrganizationCrmRelationshipDefinition(
            tenant_id=tenant_id,
            source_type=src_type,
            source_key=src_key,
            target_type=tgt_type,
            target_key=tgt_key,
            relationship_key=key,
            label=(label or key)[:128],
            inverse_label=(inverse_label or "")[:128],
            cardinality=card,
            required=bool(required),
            enabled=True,
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_relationship_created",
            resource_ids={"relationship_id": str(row.id), "key": key},
        )
        invalidate_effective_configuration(tenant_id)
        return self._serialize_def(row)

    def update_definition(
        self, tenant_id: UUID, definition_id: UUID, *, actor: str, **fields: Any
    ) -> dict[str, Any]:
        row = self._get_def(tenant_id, definition_id)
        if "label" in fields and fields["label"] is not None:
            row.label = str(fields["label"])[:128]
        if "inverse_label" in fields and fields["inverse_label"] is not None:
            row.inverse_label = str(fields["inverse_label"])[:128]
        if "enabled" in fields and fields["enabled"] is not None:
            row.enabled = bool(fields["enabled"])
        if "required" in fields and fields["required"] is not None:
            row.required = bool(fields["required"])
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_relationship_updated",
            resource_ids={"relationship_id": str(row.id)},
        )
        invalidate_effective_configuration(tenant_id)
        return self._serialize_def(row)

    def delete_definition(
        self, tenant_id: UUID, definition_id: UUID, *, actor: str
    ) -> None:
        row = self._get_def(tenant_id, definition_id)
        # Soft-disable rather than hard-delete links.
        row.enabled = False
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_relationship_disabled",
            resource_ids={"relationship_id": str(row.id)},
        )
        invalidate_effective_configuration(tenant_id)

    def link(
        self,
        tenant_id: UUID,
        *,
        relationship_key: str,
        source_record_id: UUID,
        target_record_id: UUID,
        actor: str,
    ) -> dict[str, Any]:
        definition = self._get_def_by_key(tenant_id, relationship_key)
        if not definition.enabled:
            raise DynamicCrmError("relationship_disabled", "Relationship is disabled")
        self._assert_record(
            tenant_id, definition.source_type, definition.source_key, source_record_id
        )
        self._assert_record(
            tenant_id, definition.target_type, definition.target_key, target_record_id
        )
        self._enforce_cardinality(
            tenant_id,
            definition,
            source_record_id=source_record_id,
            target_record_id=target_record_id,
        )
        existing = self._session.scalar(
            select(OrganizationCrmRelationshipLink).where(
                OrganizationCrmRelationshipLink.tenant_id == tenant_id,
                OrganizationCrmRelationshipLink.definition_id == definition.id,
                OrganizationCrmRelationshipLink.source_record_id == source_record_id,
                OrganizationCrmRelationshipLink.target_record_id == target_record_id,
            )
        )
        if existing is not None:
            return self._serialize_link(existing, definition)
        link = OrganizationCrmRelationshipLink(
            tenant_id=tenant_id,
            definition_id=definition.id,
            source_record_id=source_record_id,
            target_record_id=target_record_id,
        )
        self._session.add(link)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_relationship_link_created",
            resource_ids={
                "definition_id": str(definition.id),
                "source_record_id": str(source_record_id),
                "target_record_id": str(target_record_id),
            },
        )
        return self._serialize_link(link, definition)

    def unlink(
        self,
        tenant_id: UUID,
        *,
        relationship_key: str,
        source_record_id: UUID,
        target_record_id: UUID,
        actor: str,
    ) -> None:
        definition = self._get_def_by_key(tenant_id, relationship_key)
        link = self._session.scalar(
            select(OrganizationCrmRelationshipLink).where(
                OrganizationCrmRelationshipLink.tenant_id == tenant_id,
                OrganizationCrmRelationshipLink.definition_id == definition.id,
                OrganizationCrmRelationshipLink.source_record_id == source_record_id,
                OrganizationCrmRelationshipLink.target_record_id == target_record_id,
            )
        )
        if link is None:
            raise DynamicCrmError("not_found", "Relationship link not found")
        self._session.delete(link)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_relationship_link_removed",
            resource_ids={
                "definition_id": str(definition.id),
                "source_record_id": str(source_record_id),
                "target_record_id": str(target_record_id),
            },
        )

    def list_links_for_record(
        self,
        tenant_id: UUID,
        *,
        entity_type: str,
        entity_key: str,
        record_id: UUID,
    ) -> list[dict[str, Any]]:
        etype = entity_type.strip().lower()
        ekey = self._normalize_entity_key(etype, entity_key)
        defs = list(
            self._session.scalars(
                select(OrganizationCrmRelationshipDefinition).where(
                    OrganizationCrmRelationshipDefinition.tenant_id == tenant_id,
                    OrganizationCrmRelationshipDefinition.enabled.is_(True),
                )
            ).all()
        )
        out: list[dict[str, Any]] = []
        for definition in defs:
            if definition.source_type == etype and definition.source_key == ekey:
                links = list(
                    self._session.scalars(
                        select(OrganizationCrmRelationshipLink).where(
                            OrganizationCrmRelationshipLink.tenant_id == tenant_id,
                            OrganizationCrmRelationshipLink.definition_id
                            == definition.id,
                            OrganizationCrmRelationshipLink.source_record_id
                            == record_id,
                        )
                    ).all()
                )
                for link in links:
                    item = self._serialize_link(link, definition)
                    item["direction"] = "outgoing"
                    out.append(item)
            if definition.target_type == etype and definition.target_key == ekey:
                links = list(
                    self._session.scalars(
                        select(OrganizationCrmRelationshipLink).where(
                            OrganizationCrmRelationshipLink.tenant_id == tenant_id,
                            OrganizationCrmRelationshipLink.definition_id
                            == definition.id,
                            OrganizationCrmRelationshipLink.target_record_id
                            == record_id,
                        )
                    ).all()
                )
                for link in links:
                    item = self._serialize_link(link, definition)
                    item["direction"] = "incoming"
                    out.append(item)
        return out

    def _enforce_cardinality(
        self,
        tenant_id: UUID,
        definition: OrganizationCrmRelationshipDefinition,
        *,
        source_record_id: UUID,
        target_record_id: UUID,
    ) -> None:
        if definition.cardinality == CARDINALITY_ONE_TO_ONE:
            src_count = (
                self._session.scalar(
                    select(func.count()).where(
                        OrganizationCrmRelationshipLink.tenant_id == tenant_id,
                        OrganizationCrmRelationshipLink.definition_id == definition.id,
                        OrganizationCrmRelationshipLink.source_record_id
                        == source_record_id,
                    )
                )
                or 0
            )
            tgt_count = (
                self._session.scalar(
                    select(func.count()).where(
                        OrganizationCrmRelationshipLink.tenant_id == tenant_id,
                        OrganizationCrmRelationshipLink.definition_id == definition.id,
                        OrganizationCrmRelationshipLink.target_record_id
                        == target_record_id,
                    )
                )
                or 0
            )
            if src_count or tgt_count:
                raise DynamicCrmError(
                    "cardinality_violation",
                    "ONE_TO_ONE relationship already has a link",
                )
        elif definition.cardinality == CARDINALITY_ONE_TO_MANY:
            # Target may only belong to one source.
            tgt_count = (
                self._session.scalar(
                    select(func.count()).where(
                        OrganizationCrmRelationshipLink.tenant_id == tenant_id,
                        OrganizationCrmRelationshipLink.definition_id == definition.id,
                        OrganizationCrmRelationshipLink.target_record_id
                        == target_record_id,
                    )
                )
                or 0
            )
            if tgt_count:
                raise DynamicCrmError(
                    "cardinality_violation",
                    "Target already linked under ONE_TO_MANY",
                )
        elif definition.cardinality == CARDINALITY_MANY_TO_MANY:
            return
        else:
            raise DynamicCrmError(
                "invalid_cardinality", f"Unknown cardinality: {definition.cardinality}"
            )

    def _normalize_entity_key(self, entity_type: str, key: str) -> str:
        if entity_type == OWNER_SCOPE_MODULE:
            out = key.strip().upper()
            if out not in MODULE_KEYS:
                raise DynamicCrmError("unknown_module", f"Unknown module: {key}")
            return out
        if entity_type == OWNER_SCOPE_OBJECT:
            return key.strip().lower()
        raise DynamicCrmError(
            "invalid_entity_type", "entity type must be module|object"
        )

    def _assert_entity_exists(
        self, tenant_id: UUID, entity_type: str, entity_key: str
    ) -> None:
        if entity_type == OWNER_SCOPE_MODULE:
            kind = classify_module_entity(entity_key)
            if kind == ENTITY_KIND_CONFIGURATION_ONLY:
                # Allowed to appear in registry metadata, but not in relationship defs.
                return
            return
        row = self._session.scalar(
            select(OrganizationCustomObjectDefinition).where(
                OrganizationCustomObjectDefinition.tenant_id == tenant_id,
                OrganizationCustomObjectDefinition.object_key == entity_key,
                OrganizationCustomObjectDefinition.archived_at.is_(None),
            )
        )
        if row is None:
            raise DynamicCrmError(
                "unknown_object", f"Unknown custom object: {entity_key}"
            )

    def _assert_record(
        self,
        tenant_id: UUID,
        entity_type: str,
        entity_key: str,
        record_id: UUID,
    ) -> None:
        if entity_type == OWNER_SCOPE_OBJECT:
            definition = self._session.scalar(
                select(OrganizationCustomObjectDefinition).where(
                    OrganizationCustomObjectDefinition.tenant_id == tenant_id,
                    OrganizationCustomObjectDefinition.object_key == entity_key,
                )
            )
            if definition is None or definition.archived_at is not None:
                raise DynamicCrmError("unknown_object", "Custom object not found")
            if not definition.enabled:
                raise DynamicCrmError("object_disabled", "Custom object is disabled")
            record = self._session.scalar(
                select(OrganizationCustomObjectRecord).where(
                    OrganizationCustomObjectRecord.tenant_id == tenant_id,
                    OrganizationCustomObjectRecord.object_definition_id
                    == definition.id,
                    OrganizationCustomObjectRecord.id == record_id,
                    OrganizationCustomObjectRecord.archived_at.is_(None),
                )
            )
            if record is None:
                raise DynamicCrmError(
                    "not_found",
                    "Target/source record not found or archived",
                )
            return

        if not relationship_record_supported(
            entity_type=entity_type, entity_key=entity_key
        ):
            raise DynamicCrmError(
                "entity_not_materialized",
                f"Module {entity_key} has no record store for relationships yet",
            )

        checkers: dict[str, Any] = {
            "CUSTOMERS": (Customer, "Customer"),
            "LEADS": (Lead, "Lead"),
            "CALLS": (Call, "Call"),
            "JOBS": (Job, "Job"),
            "APPOINTMENTS": (Appointment, "Appointment"),
            "TECHNICIANS": (Technician, "Technician"),
            "PRODUCTS": (Product, "Product"),
        }
        model, label = checkers[entity_key]
        row = self._session.scalar(
            select(model).where(model.tenant_id == tenant_id, model.id == record_id)
        )
        if row is None:
            raise DynamicCrmError("not_found", f"{label} not found")
        return

    def assert_path_matches_definition(
        self,
        tenant_id: UUID,
        *,
        relationship_key: str,
        entity_type: str,
        entity_key: str,
        record_id: UUID,
    ) -> OrganizationCrmRelationshipDefinition:
        """Ensure link path entity matches the relationship definition source."""
        definition = self._get_def_by_key(tenant_id, relationship_key)
        et = entity_type.strip().lower()
        ek = self._normalize_entity_key(et, entity_key)
        if definition.source_type != et or definition.source_key != ek:
            raise DynamicCrmError(
                "relationship_mismatch",
                "Path entity does not match relationship source",
            )
        self._assert_record(tenant_id, et, ek, record_id)
        return definition

    def _get_def(
        self, tenant_id: UUID, definition_id: UUID
    ) -> OrganizationCrmRelationshipDefinition:
        row = self._session.scalar(
            select(OrganizationCrmRelationshipDefinition).where(
                OrganizationCrmRelationshipDefinition.tenant_id == tenant_id,
                OrganizationCrmRelationshipDefinition.id == definition_id,
            )
        )
        if row is None:
            raise DynamicCrmError("not_found", "Relationship not found")
        return row

    def _get_def_by_key(
        self, tenant_id: UUID, relationship_key: str
    ) -> OrganizationCrmRelationshipDefinition:
        key = relationship_key.strip().lower()
        row = self._session.scalar(
            select(OrganizationCrmRelationshipDefinition).where(
                OrganizationCrmRelationshipDefinition.tenant_id == tenant_id,
                OrganizationCrmRelationshipDefinition.relationship_key == key,
            )
        )
        if row is None:
            raise DynamicCrmError("not_found", "Relationship not found")
        return row

    def _serialize_def(
        self, row: OrganizationCrmRelationshipDefinition
    ) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "relationship_key": row.relationship_key,
            "source_type": row.source_type,
            "source_key": row.source_key,
            "target_type": row.target_type,
            "target_key": row.target_key,
            "label": row.label,
            "inverse_label": row.inverse_label,
            "cardinality": row.cardinality,
            "required": row.required,
            "enabled": row.enabled,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }

    def _serialize_link(
        self,
        link: OrganizationCrmRelationshipLink,
        definition: OrganizationCrmRelationshipDefinition,
    ) -> dict[str, Any]:
        return {
            "id": str(link.id),
            "relationship_key": definition.relationship_key,
            "definition_id": str(definition.id),
            "source_record_id": str(link.source_record_id),
            "target_record_id": str(link.target_record_id),
            "cardinality": definition.cardinality,
            "label": definition.label,
            "created_at": link.created_at.isoformat() if link.created_at else None,
        }
