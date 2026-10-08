"""AI business setup orchestration — recommend, draft, confirm via domain services."""

from __future__ import annotations

import logging
import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.ai_business_setup.errors import AiBusinessSetupError
from callbot_platform.ai_business_setup.llm import generate_recommendation
from callbot_platform.ai_business_setup.schemas import (
    ConfirmRequest,
    SetupRecommendation,
    recommendation_to_dict,
)
from callbot_platform.ai_business_setup.validate import validate_recommendation_payload
from callbot_platform.config import Settings
from callbot_platform.crm.services.catalog import ServiceCatalogOps
from callbot_platform.crm_config import CrmSetupError, CrmSetupService
from callbot_platform.db.models.services import Service
from callbot_platform.onboarding.repos import OnboardingRepository
from callbot_platform.onboarding.service import OnboardingService
from callbot_platform.organization import OrganizationError, OrganizationService
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)

STATE_KEY = "ai_business_setup"


class AiBusinessSetupService:
    def __init__(self, session: Session, *, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._onboarding = OnboardingRepository(session)

    def get_state(self, tenant_id: UUID) -> dict[str, Any]:
        row = self._onboarding.ensure(tenant_id)
        blob = dict((row.state_data or {}).get(STATE_KEY) or {})
        return {
            "status": blob.get("status") or "DRAFT",
            "description": blob.get("description"),
            "recommendation": blob.get("recommendation"),
            "operation_id": blob.get("operation_id"),
            "confirmed_at": blob.get("confirmed_at"),
            "last_confirm_result": blob.get("last_confirm_result"),
            "updated_at": blob.get("updated_at"),
        }

    def analyze(
        self,
        tenant_id: UUID,
        *,
        description: str,
        actor: str,
        clarification_answers: dict[str, str] | None = None,
    ) -> dict[str, Any]:
        cleaned = (description or "").strip()
        if len(cleaned) < 8:
            raise AiBusinessSetupError(
                "INVALID_DESCRIPTION",
                "Please describe your business in a few sentences.",
            )

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="AI_BUSINESS_SETUP_STARTED",
            resource_ids={},
            payload_summary={"description_len": len(cleaned)},
        )

        try:
            rec = generate_recommendation(
                cleaned,
                settings=self._settings,
                clarification_answers=clarification_answers,
            )
        except AiBusinessSetupError:
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="AI_BUSINESS_SETUP_FAILED",
                resource_ids={},
                payload_summary={"stage": "analyze"},
            )
            raise

        status = "CLARIFY" if rec.clarifications else "REVIEW"
        payload = recommendation_to_dict(rec)
        self._write_state(
            tenant_id,
            {
                "status": status,
                "description": cleaned,
                "recommendation": payload,
                "operation_id": secrets.token_urlsafe(16),
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="AI_BUSINESS_RECOMMENDATION_GENERATED",
            resource_ids={},
            payload_summary={
                "industry": rec.business_profile.industry,
                "modules": len(rec.modules),
                "source": rec.source,
                "clarifications": len(rec.clarifications),
            },
        )
        return self.get_state(tenant_id)

    def save_draft(
        self,
        tenant_id: UUID,
        *,
        recommendation: dict[str, Any] | SetupRecommendation,
        actor: str,
    ) -> dict[str, Any]:
        if isinstance(recommendation, SetupRecommendation):
            raw = recommendation_to_dict(recommendation)
        else:
            raw = recommendation
        rec = validate_recommendation_payload(raw)
        rec = rec.model_copy(update={"source": "edited"})
        state = self.get_state(tenant_id)
        self._write_state(
            tenant_id,
            {
                "status": "REVIEW",
                "description": state.get("description"),
                "recommendation": recommendation_to_dict(rec),
                "operation_id": state.get("operation_id") or secrets.token_urlsafe(16),
                "confirmed_at": state.get("confirmed_at"),
                "last_confirm_result": state.get("last_confirm_result"),
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="AI_BUSINESS_SETUP_REVIEWED",
            resource_ids={},
            payload_summary={
                "modules_selected": sum(1 for m in rec.modules if m.selected)
            },
        )
        return self.get_state(tenant_id)

    def confirm(
        self,
        tenant_id: UUID,
        *,
        body: ConfirmRequest,
        actor: str,
    ) -> dict[str, Any]:
        state = self.get_state(tenant_id)
        if (
            state.get("status") == "CONFIRMED"
            and state.get("operation_id") == body.operation_id
            and state.get("last_confirm_result")
        ):
            return {
                "status": "CONFIRMED",
                "idempotent": True,
                "result": state["last_confirm_result"],
            }

        rec = validate_recommendation_payload(
            recommendation_to_dict(body.recommendation)
        )
        profile = rec.business_profile
        primary_model = profile.business_models[0]

        try:
            OrganizationService(self._session).update(
                tenant_id,
                actor=actor,
                industry=profile.industry,
                business_type=primary_model,
            )
        except OrganizationError as exc:
            raise AiBusinessSetupError(exc.code, str(exc)) from exc

        result: dict[str, Any] = {
            "industry": profile.industry,
            "business_model": primary_model,
            "modules_enabled": [],
            "fields_created": 0,
            "services_created": 0,
            "services_skipped": 0,
            "ai_configuration_stored": False,
        }

        if body.apply_crm_modules:
            try:
                selected_modules = [m.key for m in rec.modules if m.selected]
                selected_fields = [
                    {
                        "module_key": f.entity,
                        "key": f.field_key,
                        "label": f.name,
                    }
                    for f in rec.custom_fields
                    if f.selected
                ]
                cfg = CrmSetupService(self._session).setup_from_recommendation(
                    tenant_id,
                    actor=actor,
                    industry_key=profile.industry,
                    business_model_key=primary_model,
                    module_keys=selected_modules,
                    custom_fields=selected_fields,
                )
                result["modules_enabled"] = [
                    m["key"] for m in (cfg.get("modules") or []) if m.get("enabled")
                ]
                result["fields_created"] = len(selected_fields)
            except CrmSetupError as exc:
                raise AiBusinessSetupError(exc.code, str(exc)) from exc

        if body.create_services:
            created, skipped = self._ensure_services(
                tenant_id,
                actor=actor,
                names=[s.name for s in rec.services if s.selected],
                descriptions={
                    s.name: s.description for s in rec.services if s.selected
                },
            )
            result["services_created"] = created
            result["services_skipped"] = skipped

        ai_blob = recommendation_to_dict(rec).get("ai_configuration") or {}
        try:
            OnboardingService(self._session).patch(
                tenant_id,
                actor=actor,
                state_data={"ai_configuration_recommendation": ai_blob},
            )
        except Exception:
            # Non-fatal — CRM config already applied
            logger.warning(
                "ai_business_setup_onboarding_patch_failed tenant_id=%s", tenant_id
            )
        for step in ("industry", "business_model", "ai_configuration"):
            try:
                OnboardingService(self._session).complete_step(
                    tenant_id, step, actor=actor
                )
            except Exception:
                continue
        result["ai_configuration_stored"] = True

        self._write_state(
            tenant_id,
            {
                "status": "CONFIRMED",
                "description": state.get("description"),
                "recommendation": recommendation_to_dict(rec),
                "operation_id": body.operation_id,
                "confirmed_at": datetime.now(UTC).isoformat(),
                "last_confirm_result": result,
                "updated_at": datetime.now(UTC).isoformat(),
            },
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="AI_BUSINESS_SETUP_CONFIRMED",
            resource_ids={"operation_id": body.operation_id},
            payload_summary={
                "industry": profile.industry,
                "modules": len(result["modules_enabled"]),
                "services_created": result["services_created"],
            },
        )
        logger.info(
            "ai_business_setup_confirmed tenant_id=%s industry=%s modules=%s",
            tenant_id,
            profile.industry,
            len(result["modules_enabled"]),
        )
        return {"status": "CONFIRMED", "idempotent": False, "result": result}

    def _ensure_services(
        self,
        tenant_id: UUID,
        *,
        actor: str,
        names: list[str],
        descriptions: dict[str, str | None],
    ) -> tuple[int, int]:
        catalog = ServiceCatalogOps(self._session)
        existing_names = {
            (r.name or "").strip().lower()
            for r in self._session.scalars(
                select(Service).where(Service.tenant_id == tenant_id)
            ).all()
        }
        created = skipped = 0
        for name in names:
            cleaned = (name or "").strip()
            if not cleaned:
                continue
            if cleaned.lower() in existing_names:
                skipped += 1
                continue
            catalog.create(
                tenant_id,
                name=cleaned,
                description=descriptions.get(cleaned),
                base_price=None,
                actor=actor,
            )
            existing_names.add(cleaned.lower())
            created += 1
        return created, skipped

    def _write_state(self, tenant_id: UUID, blob: dict[str, Any]) -> None:
        row = self._onboarding.ensure(tenant_id, for_update=True)
        data = dict(row.state_data or {})
        data[STATE_KEY] = blob
        row.state_data = data
        if row.status == "NOT_STARTED":
            row.status = "IN_PROGRESS"
            row.started_at = datetime.now(UTC)
        self._onboarding.touch(row)
