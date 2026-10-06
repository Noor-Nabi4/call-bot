"""Idempotent CRM configuration setup from industry templates."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm_templates import resolve_template, serialize_template
from callbot_platform.db.models.crm_config import (
    OrganizationCrmConfiguration,
    OrganizationCrmField,
    OrganizationCrmModule,
    OrganizationCrmStatus,
    OrganizationCrmWorkflow,
)
from callbot_platform.db.models.tenant import Tenant
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class CrmSetupError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class CrmSetupService:
    """Apply platform templates into tenant-owned CRM configuration metadata."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, tenant_id: UUID) -> dict[str, Any] | None:
        cfg = self._session.scalar(
            select(OrganizationCrmConfiguration).where(
                OrganizationCrmConfiguration.tenant_id == tenant_id
            )
        )
        if cfg is None:
            return None
        return self._serialize(cfg)

    def setup(
        self,
        tenant_id: UUID,
        *,
        actor: str,
        industry_key: str | None = None,
        business_model_key: str | None = None,
    ) -> dict[str, Any]:
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise CrmSetupError("tenant_not_found", "Organization not found")

        industry = industry_key if industry_key is not None else tenant.industry_key
        model = (
            business_model_key
            if business_model_key is not None
            else tenant.business_type
        )
        if not industry:
            raise CrmSetupError(
                "industry_required",
                "Industry must be set before CRM setup",
            )
        if not model:
            raise CrmSetupError(
                "business_model_required",
                "Business model must be set before CRM setup",
            )

        template = resolve_template(industry_key=industry, business_model=model)

        cfg = self._session.scalar(
            select(OrganizationCrmConfiguration)
            .where(OrganizationCrmConfiguration.tenant_id == tenant_id)
            .with_for_update()
        )
        now = datetime.now(UTC)
        if cfg is None:
            cfg = OrganizationCrmConfiguration(
                tenant_id=tenant_id,
                template_key=template.key,
                industry_key=industry,
                business_model_key=model,
                template_version=template.version,
                settings_json={},
            )
            self._session.add(cfg)
            self._session.flush()

        # Preserve custom settings keys; only fill missing template defaults.
        settings = dict(cfg.settings_json or {})
        for key, value in template.settings.items():
            settings.setdefault(key, value)
        cfg.settings_json = settings
        cfg.template_key = template.key
        cfg.industry_key = industry
        cfg.business_model_key = model
        cfg.template_version = template.version
        cfg.setup_completed = True
        cfg.applied_at = now
        cfg.updated_at = now

        self._ensure_modules(tenant_id, list(template.modules))
        self._ensure_statuses(tenant_id, template.statuses)
        self._ensure_fields(tenant_id, template.fields)
        self._ensure_workflows(tenant_id, template.workflows)
        self._session.flush()

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="crm_configuration_setup",
            resource_ids={
                "configuration_id": str(cfg.id),
                "template_key": template.key,
            },
            payload_summary={
                "modules": list(template.modules),
                "industry_key": industry,
                "business_model_key": model,
            },
        )
        logger.info(
            "crm_setup tenant_id=%s template=%s modules=%s",
            tenant_id,
            template.key,
            len(template.modules),
        )
        return self._serialize(cfg)

    def _ensure_modules(self, tenant_id: UUID, modules: list[str]) -> None:
        existing = {
            r.module_key: r
            for r in self._session.scalars(
                select(OrganizationCrmModule).where(
                    OrganizationCrmModule.tenant_id == tenant_id
                )
            ).all()
        }
        now = datetime.now(UTC)
        for key in modules:
            row = existing.get(key)
            if row is None:
                self._session.add(
                    OrganizationCrmModule(
                        tenant_id=tenant_id,
                        module_key=key,
                        enabled=True,
                        source="template",
                    )
                )
            elif row.source == "template":
                # Do not force-enable if user disabled a template module.
                row.updated_at = now

    def _ensure_statuses(
        self, tenant_id: UUID, statuses: dict[str, tuple[str, ...]]
    ) -> None:
        existing = {
            (r.module_key, r.status_key): r
            for r in self._session.scalars(
                select(OrganizationCrmStatus).where(
                    OrganizationCrmStatus.tenant_id == tenant_id
                )
            ).all()
        }
        for module_key, keys in statuses.items():
            for idx, status_key in enumerate(keys):
                if (module_key, status_key) in existing:
                    continue
                self._session.add(
                    OrganizationCrmStatus(
                        tenant_id=tenant_id,
                        module_key=module_key,
                        status_key=status_key,
                        sort_order=idx,
                        source="template",
                    )
                )

    def _ensure_fields(
        self,
        tenant_id: UUID,
        fields: dict[str, tuple[dict[str, str], ...]],
    ) -> None:
        existing = {
            (r.module_key, r.field_key): r
            for r in self._session.scalars(
                select(OrganizationCrmField).where(
                    OrganizationCrmField.tenant_id == tenant_id
                )
            ).all()
        }
        for module_key, defs in fields.items():
            for item in defs:
                field_key = item["key"]
                if (module_key, field_key) in existing:
                    continue
                self._session.add(
                    OrganizationCrmField(
                        tenant_id=tenant_id,
                        module_key=module_key,
                        field_key=field_key,
                        label=item.get("label") or field_key,
                        source="template",
                    )
                )

    def _ensure_workflows(
        self, tenant_id: UUID, workflows: tuple[dict[str, Any], ...]
    ) -> None:
        existing = {
            r.workflow_key: r
            for r in self._session.scalars(
                select(OrganizationCrmWorkflow).where(
                    OrganizationCrmWorkflow.tenant_id == tenant_id
                )
            ).all()
        }
        for wf in workflows:
            key = str(wf["key"])
            if key in existing:
                continue
            self._session.add(
                OrganizationCrmWorkflow(
                    tenant_id=tenant_id,
                    workflow_key=key,
                    name=str(wf.get("name") or key),
                    module_key=wf.get("module_key"),
                    stages_json=list(wf.get("stages") or []),
                    source="template",
                    definition_json=dict(wf),
                )
            )

    def _serialize(self, cfg: OrganizationCrmConfiguration) -> dict[str, Any]:
        modules = list(
            self._session.scalars(
                select(OrganizationCrmModule)
                .where(OrganizationCrmModule.tenant_id == cfg.tenant_id)
                .order_by(OrganizationCrmModule.module_key)
            ).all()
        )
        statuses = list(
            self._session.scalars(
                select(OrganizationCrmStatus)
                .where(OrganizationCrmStatus.tenant_id == cfg.tenant_id)
                .order_by(
                    OrganizationCrmStatus.module_key,
                    OrganizationCrmStatus.sort_order,
                )
            ).all()
        )
        fields = list(
            self._session.scalars(
                select(OrganizationCrmField)
                .where(OrganizationCrmField.tenant_id == cfg.tenant_id)
                .order_by(
                    OrganizationCrmField.module_key, OrganizationCrmField.field_key
                )
            ).all()
        )
        workflows = list(
            self._session.scalars(
                select(OrganizationCrmWorkflow)
                .where(OrganizationCrmWorkflow.tenant_id == cfg.tenant_id)
                .order_by(OrganizationCrmWorkflow.workflow_key)
            ).all()
        )
        return {
            "id": str(cfg.id),
            "tenant_id": str(cfg.tenant_id),
            "template_key": cfg.template_key,
            "industry_key": cfg.industry_key,
            "business_model_key": cfg.business_model_key,
            "template_version": cfg.template_version,
            "setup_completed": cfg.setup_completed,
            "settings": dict(cfg.settings_json or {}),
            "modules": [
                {
                    "key": m.module_key,
                    "enabled": m.enabled,
                    "source": m.source,
                }
                for m in modules
            ],
            "statuses": [
                {
                    "module_key": s.module_key,
                    "key": s.status_key,
                    "sort_order": s.sort_order,
                    "source": s.source,
                }
                for s in statuses
            ],
            "fields": [
                {
                    "module_key": f.module_key,
                    "key": f.field_key,
                    "label": f.label,
                    "source": f.source,
                }
                for f in fields
            ],
            "workflows": [
                {
                    "key": w.workflow_key,
                    "name": w.name,
                    "module_key": w.module_key,
                    "stages": list(w.stages_json or []),
                    "source": w.source,
                }
                for w in workflows
            ],
            "applied_at": cfg.applied_at.isoformat() if cfg.applied_at else None,
            "updated_at": cfg.updated_at.isoformat() if cfg.updated_at else None,
            "resolved_template": serialize_template(
                resolve_template(
                    industry_key=cfg.industry_key,
                    business_model=cfg.business_model_key,
                )
            ),
        }
