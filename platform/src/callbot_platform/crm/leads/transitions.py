"""Lead status transition policy and service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.leads.activities import LeadActivityService
from callbot_platform.crm.leads.constants import (
    STATUS_ACTIVITY_TYPES,
    VALID_TRANSITIONS,
    LeadActivityType,
)
from callbot_platform.crm.leads.normalize import normalize_status
from callbot_platform.crm.leads.serialize import serialize_lead
from callbot_platform.db.models import Lead
from callbot_platform.telephony.audit import write_audit


class LeadTransitionService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._activities = LeadActivityService(session)

    def transition(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        *,
        to_status: str,
        actor: str,
        actor_user_id: UUID | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        lead = self._session.scalar(
            select(Lead)
            .where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
            .with_for_update()
        )
        if lead is None:
            raise CrmError("not_found", "Lead not found for tenant")
        if lead.archived_at is not None:
            raise CrmError("lead_archived", "Cannot transition an archived lead")

        target = normalize_status(to_status)
        current = normalize_status(lead.status)
        if current == target:
            return serialize_lead(lead)

        if (current, target) not in VALID_TRANSITIONS:
            raise CrmError(
                "invalid_transition",
                f"Transition from {current} to {target} is not allowed",
            )

        lead.status = target
        lead.updated_by = actor
        lead.updated_at = datetime.now(UTC)
        self._session.flush()

        meta: dict[str, Any] = {"from": current, "to": target}
        if reason:
            meta["reason"] = reason[:500]

        self._activities.record(
            tenant_id,
            lead_id,
            activity_type=LeadActivityType.STATUS_CHANGED.value,
            actor=actor,
            actor_user_id=actor_user_id,
            metadata=meta,
        )
        notable = STATUS_ACTIVITY_TYPES.get(target)
        if notable:
            self._activities.record(
                tenant_id,
                lead_id,
                activity_type=notable,
                actor=actor,
                actor_user_id=actor_user_id,
                metadata=meta,
            )

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="lead_status_changed",
            resource_ids={
                "lead_id": str(lead.id),
                "from": current,
                "to": target,
            },
        )
        return serialize_lead(lead)
