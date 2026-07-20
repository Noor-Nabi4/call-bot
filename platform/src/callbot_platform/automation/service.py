"""Automation rule evaluation and CRUD."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models import AutomationRule
from callbot_platform.jobs.repos.job_repo import JobRepository
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)

VALID_TRIGGERS = frozenset(
    {
        "call.ended",
        "call.handoff_requested",
        "appointment.created",
    }
)
VALID_ACTIONS = frozenset(
    {
        "write_audit",
        "create_follow_up_job",
    }
)


class AutomationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class AutomationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_rules(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(AutomationRule)
            .where(AutomationRule.tenant_id == tenant_id)
            .order_by(AutomationRule.created_at.desc())
        ).all()
        return [self._serialize(r) for r in rows]

    def create_rule(
        self,
        tenant_id: UUID,
        *,
        name: str,
        trigger_key: str,
        action_key: str,
        description: str | None = None,
        config: dict[str, Any] | None = None,
        is_enabled: bool = True,
        actor: str = "ops",
    ) -> dict[str, Any]:
        cleaned = name.strip()
        if not cleaned:
            raise AutomationError("invalid_name", "Name is required")
        if trigger_key not in VALID_TRIGGERS:
            raise AutomationError(
                "invalid_trigger",
                f"trigger_key must be one of {sorted(VALID_TRIGGERS)}",
            )
        if action_key not in VALID_ACTIONS:
            raise AutomationError(
                "invalid_action",
                f"action_key must be one of {sorted(VALID_ACTIONS)}",
            )
        existing = self._session.scalar(
            select(AutomationRule).where(
                AutomationRule.tenant_id == tenant_id,
                AutomationRule.name == cleaned,
            )
        )
        if existing is not None:
            raise AutomationError("name_taken", "A rule with that name already exists")
        row = AutomationRule(
            tenant_id=tenant_id,
            name=cleaned[:128],
            description=(description or "").strip() or None,
            trigger_key=trigger_key,
            action_key=action_key,
            config=dict(config or {}),
            is_enabled=is_enabled,
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="automation_rule_created",
            resource_ids={"rule_id": str(row.id), "trigger": trigger_key},
        )
        return self._serialize(row)

    def update_rule(
        self,
        tenant_id: UUID,
        rule_id: UUID,
        *,
        name: str | None = None,
        description: str | None = None,
        trigger_key: str | None = None,
        action_key: str | None = None,
        config: dict[str, Any] | None = None,
        is_enabled: bool | None = None,
        actor: str = "ops",
    ) -> dict[str, Any]:
        row = self._get(tenant_id, rule_id)
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise AutomationError("invalid_name", "Name is required")
            clash = self._session.scalar(
                select(AutomationRule).where(
                    AutomationRule.tenant_id == tenant_id,
                    AutomationRule.name == cleaned,
                    AutomationRule.id != rule_id,
                )
            )
            if clash is not None:
                raise AutomationError(
                    "name_taken", "A rule with that name already exists"
                )
            row.name = cleaned[:128]
        if description is not None:
            row.description = description.strip() or None
        if trigger_key is not None:
            if trigger_key not in VALID_TRIGGERS:
                raise AutomationError(
                    "invalid_trigger",
                    f"trigger_key must be one of {sorted(VALID_TRIGGERS)}",
                )
            row.trigger_key = trigger_key
        if action_key is not None:
            if action_key not in VALID_ACTIONS:
                raise AutomationError(
                    "invalid_action",
                    f"action_key must be one of {sorted(VALID_ACTIONS)}",
                )
            row.action_key = action_key
        if config is not None:
            row.config = dict(config)
        if is_enabled is not None:
            row.is_enabled = is_enabled
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="automation_rule_updated",
            resource_ids={"rule_id": str(row.id)},
        )
        return self._serialize(row)

    def delete_rule(
        self, tenant_id: UUID, rule_id: UUID, *, actor: str = "ops"
    ) -> None:
        row = self._get(tenant_id, rule_id)
        self._session.delete(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="automation_rule_deleted",
            resource_ids={"rule_id": str(rule_id)},
        )

    def catalog(self) -> dict[str, Any]:
        return {
            "triggers": [
                {
                    "key": "call.ended",
                    "label": "Call ended",
                    "description": "Fires when a voice call is closed.",
                },
                {
                    "key": "call.handoff_requested",
                    "label": "Handoff requested",
                    "description": "Fires when call metrics mark a human handoff.",
                },
                {
                    "key": "appointment.created",
                    "label": "Appointment created",
                    "description": "Fires after a new appointment is booked.",
                },
            ],
            "actions": [
                {
                    "key": "write_audit",
                    "label": "Write audit event",
                    "description": "Record a structured audit entry for ops review.",
                },
                {
                    "key": "create_follow_up_job",
                    "label": "Create follow-up job",
                    "description": (
                        "Create an unassigned dispatch job when a customer is known."
                    ),
                },
            ],
        }

    def dispatch(
        self,
        tenant_id: UUID,
        trigger_key: str,
        *,
        payload: dict[str, Any],
    ) -> list[dict[str, Any]]:
        """Run enabled rules for a trigger. Failures are logged; never raise to callers."""
        if trigger_key not in VALID_TRIGGERS:
            return []
        rows = self._session.scalars(
            select(AutomationRule).where(
                AutomationRule.tenant_id == tenant_id,
                AutomationRule.trigger_key == trigger_key,
                AutomationRule.is_enabled.is_(True),
            )
        ).all()
        results: list[dict[str, Any]] = []
        for row in rows:
            try:
                outcome = self._run_action(row, payload)
                results.append(
                    {
                        "rule_id": str(row.id),
                        "action_key": row.action_key,
                        "ok": True,
                        "result": outcome,
                    }
                )
            except Exception:
                logger.exception(
                    "automation_rule_failed",
                    extra={
                        "tenant_id": str(tenant_id),
                        "rule_id": str(row.id),
                        "trigger": trigger_key,
                    },
                )
                results.append(
                    {
                        "rule_id": str(row.id),
                        "action_key": row.action_key,
                        "ok": False,
                    }
                )
        return results

    def _run_action(
        self, row: AutomationRule, payload: dict[str, Any]
    ) -> dict[str, Any]:
        if row.action_key == "write_audit":
            write_audit(
                self._session,
                tenant_id=row.tenant_id,
                actor="automation",
                action="automation_fired",
                resource_ids={
                    "rule_id": str(row.id),
                    "trigger": row.trigger_key,
                    **{
                        k: str(v)
                        for k, v in payload.items()
                        if k.endswith("_id") and v is not None
                    },
                },
                payload_summary={
                    "rule_name": row.name,
                    "trigger": row.trigger_key,
                    "keys": sorted(payload.keys()),
                },
            )
            return {"audit": True}

        if row.action_key == "create_follow_up_job":
            customer_id = payload.get("customer_id")
            if not customer_id:
                return {"skipped": "customer_required"}
            service_type = str(
                (row.config or {}).get("service_type") or "Automated follow-up"
            )[:128]
            job = JobRepository(self._session).create(
                row.tenant_id,
                customer_id=UUID(str(customer_id)),
                service_type=service_type,
                status="new",
                call_id=(
                    UUID(str(payload["call_id"])) if payload.get("call_id") else None
                ),
                actor="automation",
            )
            return {"job_id": job["id"]}

        raise AutomationError("invalid_action", f"Unknown action {row.action_key}")

    def _get(self, tenant_id: UUID, rule_id: UUID) -> AutomationRule:
        row = self._session.scalar(
            select(AutomationRule).where(
                AutomationRule.id == rule_id,
                AutomationRule.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise AutomationError("not_found", "Automation rule not found")
        return row

    def _serialize(self, row: AutomationRule) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "name": row.name,
            "description": row.description,
            "trigger_key": row.trigger_key,
            "action_key": row.action_key,
            "config": row.config or {},
            "is_enabled": row.is_enabled,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
