"""Organization CRM module enable/disable/reorder."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.business_config.modules import (
    MODULE_BY_KEY,
    MODULE_KEYS,
    SOURCE_ORG_CUSTOM,
    normalize_source,
    serialize_module,
)
from callbot_platform.db.models.crm_config import OrganizationCrmModule
from callbot_platform.dynamic_crm.config_cache import invalidate_effective_configuration
from callbot_platform.dynamic_crm.errors import DynamicCrmError
from callbot_platform.telephony.audit import write_audit


class ModuleConfigService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_modules(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = {
            r.module_key: r
            for r in self._session.scalars(
                select(OrganizationCrmModule).where(
                    OrganizationCrmModule.tenant_id == tenant_id
                )
            ).all()
        }
        out: list[dict[str, Any]] = []
        for key, meta in MODULE_BY_KEY.items():
            row = rows.get(key)
            item = serialize_module(meta)
            if row is None:
                item.update(
                    {
                        "enabled": False,
                        "display_order": meta.default_order,
                        "source": None,
                        "configured": False,
                    }
                )
            else:
                item.update(
                    {
                        "enabled": bool(row.enabled),
                        "display_order": int(row.display_order),
                        "source": normalize_source(row.source),
                        "configured": True,
                        "id": str(row.id),
                    }
                )
            out.append(item)
        out.sort(key=lambda m: (m["display_order"], m["name"]))
        return out

    def _get_row(self, tenant_id: UUID, module_key: str) -> OrganizationCrmModule:
        key = module_key.strip().upper()
        if key not in MODULE_KEYS:
            raise DynamicCrmError("unknown_module", f"Unknown module: {module_key}")
        row = self._session.scalar(
            select(OrganizationCrmModule).where(
                OrganizationCrmModule.tenant_id == tenant_id,
                OrganizationCrmModule.module_key == key,
            )
        )
        if row is None:
            meta = MODULE_BY_KEY[key]
            row = OrganizationCrmModule(
                tenant_id=tenant_id,
                module_key=key,
                enabled=False,
                display_order=meta.default_order,
                source=SOURCE_ORG_CUSTOM,
            )
            self._session.add(row)
            self._session.flush()
        return row

    def set_enabled(
        self, tenant_id: UUID, module_key: str, *, enabled: bool, actor: str
    ) -> dict[str, Any]:
        key = module_key.strip().upper()
        meta = MODULE_BY_KEY.get(key)
        if meta is None:
            raise DynamicCrmError("unknown_module", f"Unknown module: {module_key}")
        if meta.required and not enabled:
            raise DynamicCrmError(
                "module_required",
                f"Module {key} is required and cannot be disabled",
            )
        if enabled and not meta.ui_live:
            raise DynamicCrmError(
                "module_not_available",
                f"Module {key} is not available yet for this workspace",
            )
        row = self._get_row(tenant_id, key)
        before = row.enabled
        row.enabled = enabled
        row.source = SOURCE_ORG_CUSTOM
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_module_enabled" if enabled else "crm_module_disabled",
            resource_ids={"module_key": key},
            payload_summary={"before": before, "after": enabled},
        )
        invalidate_effective_configuration(tenant_id)
        return next(m for m in self.list_modules(tenant_id) if m["key"] == key)

    def reorder(
        self, tenant_id: UUID, ordered_keys: list[str], *, actor: str
    ) -> list[dict[str, Any]]:
        keys = [k.strip().upper() for k in ordered_keys]
        if len(keys) != len(set(keys)):
            raise DynamicCrmError("duplicate_module", "Duplicate module keys in order")
        for key in keys:
            if key not in MODULE_KEYS:
                raise DynamicCrmError("unknown_module", f"Unknown module: {key}")
            row = self._get_row(tenant_id, key)
            row.display_order = (keys.index(key) + 1) * 10
            row.source = SOURCE_ORG_CUSTOM
            row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_modules_reordered",
            resource_ids={},
            payload_summary={"order": keys},
        )
        invalidate_effective_configuration(tenant_id)
        return self.list_modules(tenant_id)

    def require_enabled(self, tenant_id: UUID, module_key: str) -> None:
        key = module_key.strip().upper()
        if key not in MODULE_KEYS:
            raise DynamicCrmError("unknown_module", f"Unknown module: {module_key}")
        row = self._session.scalar(
            select(OrganizationCrmModule).where(
                OrganizationCrmModule.tenant_id == tenant_id,
                OrganizationCrmModule.module_key == key,
            )
        )
        if row is None or not row.enabled:
            raise DynamicCrmError(
                "module_disabled",
                f"Module {key} is not enabled for this organization",
            )
