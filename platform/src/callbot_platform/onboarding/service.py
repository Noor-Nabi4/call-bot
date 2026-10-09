"""Tenant-scoped organization onboarding service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.onboarding.errors import OnboardingError
from callbot_platform.onboarding.repos import OnboardingRepository
from callbot_platform.onboarding.status import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_NOT_STARTED,
    STATUS_SKIPPED,
    assert_can_mutate,
    assert_can_transition,
)
from callbot_platform.onboarding.steps import (
    OPTIONAL_STEPS,
    REQUIRED_STEPS,
    STEP_BY_KEY,
    STEP_ORDER,
    known_step,
    list_step_defs,
)
from callbot_platform.telephony.audit import write_audit


def _as_str_list(value: Any) -> list[str]:
    if not isinstance(value, list):
        return []
    out: list[str] = []
    seen: set[str] = set()
    for item in value:
        if not isinstance(item, str):
            continue
        key = item.strip()
        if not key or key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out


def _ordered_unique(keys: list[str]) -> list[str]:
    order_index = {k: i for i, k in enumerate(STEP_ORDER)}
    known = [k for k in keys if k in order_index]
    unknown = [k for k in keys if k not in order_index]
    known.sort(key=lambda k: order_index[k])
    return known + unknown


class OnboardingService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = OnboardingRepository(session)

    def get(self, tenant_id: UUID) -> dict[str, Any]:
        row = self._repo.ensure(tenant_id)
        return self._serialize(row)

    def patch(
        self,
        tenant_id: UUID,
        *,
        actor: str,
        current_step: str | None = None,
        state_data: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = self._repo.ensure(tenant_id, for_update=True)
        assert_can_mutate(row.status)
        changed: list[str] = []

        if current_step is not None:
            cleaned = current_step.strip()
            if cleaned and not known_step(cleaned):
                raise OnboardingError("invalid_step", f"Unknown step: {cleaned}")
            row.current_step = cleaned or None
            changed.append("current_step")

        if state_data is not None:
            if not isinstance(state_data, dict):
                raise OnboardingError(
                    "invalid_state_data", "state_data must be an object"
                )
            # Shallow merge — wizard drafts only; domain data stays in domain tables.
            merged = dict(row.state_data or {})
            for key, value in state_data.items():
                if not isinstance(key, str) or not key.strip():
                    continue
                cleaned_key = key.strip()
                if (
                    cleaned_key == "setup_path"
                    and value is not None
                    and value not in {"ai", "manual"}
                ):
                    raise OnboardingError(
                        "invalid_setup_path",
                        "setup_path must be 'ai' or 'manual'",
                    )
                if value is None:
                    merged.pop(cleaned_key, None)
                else:
                    merged[cleaned_key] = value
            row.state_data = merged
            changed.append("state_data")

        if not changed:
            raise OnboardingError("empty_patch", "No onboarding fields to update")

        self._mark_started(row)
        self._recompute(row)
        self._repo.touch(row)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="onboarding_patched",
            resource_ids={"onboarding_id": str(row.id)},
            payload_summary={"changed_fields": changed},
        )
        return self._serialize(row)

    def complete_step(
        self,
        tenant_id: UUID,
        step: str,
        *,
        actor: str,
        allow_auto_complete: bool = True,
    ) -> dict[str, Any]:
        key = step.strip()
        if not known_step(key):
            raise OnboardingError("invalid_step", f"Unknown step: {key}")
        row = self._repo.ensure(tenant_id, for_update=True)
        assert_can_mutate(row.status)

        completed = _as_str_list(row.completed_steps)
        skipped = _as_str_list(row.skipped_steps)
        if key not in completed:
            completed.append(key)
        if key in skipped:
            skipped = [s for s in skipped if s != key]
        row.completed_steps = _ordered_unique(completed)
        row.skipped_steps = _ordered_unique(skipped)

        self._mark_started(row)
        self._advance_current(row, key)
        self._recompute(row)
        self._repo.touch(row)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="onboarding_step_completed",
            resource_ids={"onboarding_id": str(row.id), "step": key},
        )
        # Single completion path: mark_completed owns CRM + COMPLETED.
        # Callers that finalize via mark_completed() pass allow_auto_complete=False.
        if allow_auto_complete and REQUIRED_STEPS.issubset(
            set(_as_str_list(row.completed_steps))
        ):
            return self.mark_completed(tenant_id, actor=actor)
        return self._serialize(row)

    def skip_step(self, tenant_id: UUID, step: str, *, actor: str) -> dict[str, Any]:
        key = step.strip()
        if not known_step(key):
            raise OnboardingError("invalid_step", f"Unknown step: {key}")
        if key in REQUIRED_STEPS:
            raise OnboardingError(
                "step_required",
                f"Step '{key}' is required and cannot be skipped",
            )
        row = self._repo.ensure(tenant_id, for_update=True)
        assert_can_mutate(row.status)

        completed = _as_str_list(row.completed_steps)
        skipped = _as_str_list(row.skipped_steps)
        if key not in skipped:
            skipped.append(key)
        if key in completed:
            completed = [c for c in completed if c != key]
        row.completed_steps = _ordered_unique(completed)
        row.skipped_steps = _ordered_unique(skipped)

        self._mark_started(row)
        self._advance_current(row, key)
        self._recompute(row)
        self._repo.touch(row)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="onboarding_step_skipped",
            resource_ids={"onboarding_id": str(row.id), "step": key},
        )
        return self._serialize(row)

    def mark_completed(self, tenant_id: UUID, *, actor: str) -> dict[str, Any]:
        row = self._repo.ensure(tenant_id, for_update=True)
        if row.status == STATUS_COMPLETED:
            return self._serialize(row)
        assert_can_transition(row.status, STATUS_COMPLETED)
        completed = set(_as_str_list(row.completed_steps))
        missing = sorted(REQUIRED_STEPS - completed)
        if missing:
            raise OnboardingError(
                "incomplete",
                f"Required steps not completed: {', '.join(missing)}",
            )
        self._require_business_ready(tenant_id)
        self._run_crm_setup(tenant_id, actor=actor)
        row.status = STATUS_COMPLETED
        row.completed_at = datetime.now(UTC)
        self._recompute(row)
        self._repo.touch(row)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="onboarding_completed",
            resource_ids={"onboarding_id": str(row.id)},
        )
        return self._serialize(row)

    def _require_business_ready(self, tenant_id: UUID) -> None:
        from callbot_platform.db.models.tenant import Tenant

        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise OnboardingError("not_found", "Organization not found")
        if not (tenant.name or "").strip():
            raise OnboardingError(
                "profile_incomplete", "Business name is required before completion"
            )
        if not tenant.industry_key:
            raise OnboardingError(
                "profile_incomplete", "Industry is required before completion"
            )
        if not tenant.business_type:
            raise OnboardingError(
                "profile_incomplete", "Business model is required before completion"
            )

    def _run_crm_setup(self, tenant_id: UUID, *, actor: str) -> None:
        from callbot_platform.crm_config import CrmSetupError, CrmSetupService

        try:
            CrmSetupService(self._session).setup(tenant_id, actor=actor)
        except CrmSetupError as exc:
            raise OnboardingError(exc.code, str(exc)) from exc

    def mark_skipped(self, tenant_id: UUID, *, actor: str) -> dict[str, Any]:
        """Rejected under mandatory onboarding — SKIPPED does not grant access.

        Historical SKIPPED rows remain readable; clients must resume and complete.
        """
        del tenant_id, actor  # API-compatible signature; never mutates state.
        raise OnboardingError(
            "mandatory_onboarding",
            "Organization onboarding is mandatory and cannot be skipped",
        )

    def _mark_started(self, row: Any) -> None:
        if row.status == STATUS_NOT_STARTED:
            row.status = STATUS_IN_PROGRESS
            row.started_at = datetime.now(UTC)
            if row.current_step is None:
                row.current_step = STEP_ORDER[0]
        elif row.status == STATUS_SKIPPED:
            # Resume previously skipped orgs so they can finish mandatory setup.
            row.status = STATUS_IN_PROGRESS
            if row.started_at is None:
                row.started_at = datetime.now(UTC)
            if row.current_step is None:
                pending = self._pending_steps(row)
                row.current_step = pending[0] if pending else STEP_ORDER[0]
            row.completed_at = None

    def _advance_current(self, row: Any, settled_step: str) -> None:
        pending = self._pending_steps(row)
        if pending:
            row.current_step = pending[0]
        elif settled_step in STEP_BY_KEY:
            row.current_step = settled_step

    def _pending_steps(self, row: Any) -> list[str]:
        completed = set(_as_str_list(row.completed_steps))
        skipped = set(_as_str_list(row.skipped_steps))
        settled = completed | skipped
        return [k for k in STEP_ORDER if k not in settled]

    def _recompute(self, row: Any) -> None:
        completed = _ordered_unique(_as_str_list(row.completed_steps))
        skipped = _ordered_unique(
            [s for s in _as_str_list(row.skipped_steps) if s in OPTIONAL_STEPS]
        )
        # Drop unknown / required-from-skipped pollution
        completed = [c for c in completed if c in STEP_BY_KEY]
        row.completed_steps = completed
        row.skipped_steps = skipped

        total = len(STEP_ORDER)
        settled = set(completed) | set(skipped)
        settled_count = sum(1 for k in STEP_ORDER if k in settled)
        row.progress_percent = 0 if total == 0 else round(100 * settled_count / total)

        # Repair stale current_step
        if (row.current_step and row.current_step not in STEP_BY_KEY) or (
            row.status == STATUS_IN_PROGRESS and row.current_step is None
        ):
            pending = self._pending_steps(row)
            row.current_step = pending[0] if pending else STEP_ORDER[-1]

    def _serialize(self, row: Any) -> dict[str, Any]:
        self._recompute(row)
        completed = list(row.completed_steps or [])
        skipped = list(row.skipped_steps or [])
        settled = set(completed) | set(skipped)
        steps_out: list[dict[str, Any]] = []
        for s in list_step_defs():
            key = str(s["key"])
            if key in completed:
                state = "completed"
            elif key in skipped:
                state = "skipped"
            else:
                state = "pending"
            steps_out.append({**s, "state": state})

        pending = [k for k in STEP_ORDER if k not in settled]
        resume_step = row.current_step
        if resume_step not in STEP_BY_KEY or resume_step in settled:
            resume_step = pending[0] if pending else None

        can_resume = (
            row.status in {STATUS_IN_PROGRESS, STATUS_SKIPPED}
            and resume_step is not None
        )
        total = len(STEP_ORDER)
        settled_count = sum(1 for k in STEP_ORDER if k in settled)

        data = {
            "status": row.status,
            "current_step": row.current_step,
            "resume_step": resume_step,
            "completed_steps": completed,
            "skipped_steps": skipped,
            "progress_percent": int(row.progress_percent or 0),
            "completed_count": settled_count,
            "total_count": total,
            "required_remaining": sorted(REQUIRED_STEPS - set(completed)),
            "can_resume": can_resume,
            "steps": steps_out,
            "state_data": dict(row.state_data or {}),
        }
        data.update(self._repo.serialize_row_meta(row))
        return data
