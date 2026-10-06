"""Estimate status transition policy."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.estimates.constants import (
    ESTIMATE_STATUSES,
    VALID_TRANSITIONS,
    EstimateStatus,
)
from callbot_platform.crm.estimates.serialize import (
    serialize_estimate,
    serialize_status_history,
)
from callbot_platform.db.models.estimates import Estimate, EstimateStatusHistory
from callbot_platform.telephony.audit import write_audit


def normalize_status(value: str) -> str:
    raw = (value or "").strip().upper()
    if raw not in ESTIMATE_STATUSES:
        raise CrmError("invalid_status", f"Unknown estimate status: {value}")
    return raw


def is_expired(estimate: Estimate, *, now: datetime | None = None) -> bool:
    if estimate.valid_until is None:
        return False
    at = now or datetime.now(UTC)
    if at.tzinfo is None:
        at = at.replace(tzinfo=UTC)
    valid = estimate.valid_until
    if valid.tzinfo is None:
        valid = valid.replace(tzinfo=UTC)
    return valid < at


class EstimateTransitionService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def history(self, tenant_id: UUID, estimate_id: UUID) -> list[dict[str, Any]]:
        estimate = self._session.scalar(
            select(Estimate).where(
                Estimate.id == estimate_id, Estimate.tenant_id == tenant_id
            )
        )
        if estimate is None:
            raise CrmError("not_found", "Estimate not found for tenant")
        rows = list(
            self._session.scalars(
                select(EstimateStatusHistory)
                .where(
                    EstimateStatusHistory.tenant_id == tenant_id,
                    EstimateStatusHistory.estimate_id == estimate_id,
                )
                .order_by(
                    EstimateStatusHistory.created_at.asc(),
                    EstimateStatusHistory.id.asc(),
                )
            ).all()
        )
        return [serialize_status_history(r) for r in rows]

    def transition(
        self,
        tenant_id: UUID,
        estimate_id: UUID,
        *,
        to_status: str,
        actor: str,
        reason: str | None = None,
        metadata: dict[str, Any] | None = None,
        skip_expiry_check: bool = False,
    ) -> dict[str, Any]:
        estimate = self._session.scalar(
            select(Estimate)
            .where(Estimate.id == estimate_id, Estimate.tenant_id == tenant_id)
            .options(
                selectinload(Estimate.items),
                selectinload(Estimate.status_history),
                selectinload(Estimate.customer),
                selectinload(Estimate.location),
                selectinload(Estimate.conversions),
            )
            .with_for_update()
        )
        if estimate is None:
            raise CrmError("not_found", "Estimate not found for tenant")
        if estimate.archived_at is not None:
            raise CrmError("estimate_archived", "Estimate is archived")

        target = normalize_status(to_status)
        current = estimate.status
        if current == target:
            return serialize_estimate(
                estimate, include_history=True, include_conversions=True
            )
        if (current, target) not in VALID_TRANSITIONS:
            raise CrmError(
                "invalid_transition",
                f"Cannot transition estimate from {current} to {target}",
            )

        if (
            not skip_expiry_check
            and target
            in {
                EstimateStatus.APPROVED.value,
                EstimateStatus.CONVERTED.value,
            }
            and is_expired(estimate)
        ):
            raise CrmError("estimate_expired", "Estimate is past valid_until")

        if target == EstimateStatus.EXPIRED.value and not is_expired(estimate):
            raise CrmError(
                "estimate_not_expired",
                "Estimate is still within valid_until",
            )

        now = datetime.now(UTC)
        prev = estimate.status
        estimate.status = target
        estimate.updated_by = actor
        estimate.updated_at = now

        if target == EstimateStatus.APPROVED.value:
            estimate.approved_at = now
            estimate.approved_by = actor
        if target == EstimateStatus.REJECTED.value:
            estimate.rejected_at = now
            estimate.rejected_by = actor
            if reason:
                estimate.rejection_reason = reason.strip()[:2000] or None
        if target == EstimateStatus.CONVERTED.value:
            estimate.converted_at = now

        self._session.add(
            EstimateStatusHistory(
                tenant_id=tenant_id,
                estimate_id=estimate.id,
                from_status=prev,
                to_status=target,
                changed_by=actor,
                reason=(reason.strip()[:500] if reason and reason.strip() else None),
                metadata_json=metadata or {},
            )
        )
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="estimate_status_changed",
            resource_ids={
                "estimate_id": str(estimate.id),
                "from_status": prev,
                "to_status": target,
            },
            payload_summary={"reason": reason} if reason else None,
        )
        return serialize_estimate(
            estimate, include_history=True, include_conversions=True
        )
