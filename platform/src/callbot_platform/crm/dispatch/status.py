"""Technician operational status service (Phase 12)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.dispatch.constants import (
    DEFAULT_TECHNICIAN_STATUS,
    DISPATCH_EVENT_TECHNICIAN_STATUS_CHANGED,
    TECHNICIAN_OPERATIONAL_STATUSES,
    VALID_TECH_STATUS_TRANSITIONS,
    normalize_tech_status,
)
from callbot_platform.crm.dispatch.events import emit_dispatch_event
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.dispatch import (
    TechnicianOperationalStatus,
    TechnicianStatusHistory,
)
from callbot_platform.db.models.jobs import Technician
from callbot_platform.telephony.audit import write_audit


class TechnicianStatusService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _require_technician(self, tenant_id: UUID, technician_id: UUID) -> Technician:
        row = self._session.scalar(
            select(Technician).where(
                Technician.id == technician_id, Technician.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("technician_not_found", "Technician not found for tenant")
        return row

    def ensure_row(
        self,
        tenant_id: UUID,
        technician_id: UUID,
        *,
        actor: str | None = None,
        initial_status: str | None = None,
    ) -> TechnicianOperationalStatus:
        self._require_technician(tenant_id, technician_id)
        row = self._session.scalar(
            select(TechnicianOperationalStatus)
            .where(
                TechnicianOperationalStatus.tenant_id == tenant_id,
                TechnicianOperationalStatus.technician_id == technician_id,
            )
            .with_for_update()
        )
        if row is not None:
            return row
        now = datetime.now(UTC)
        status = initial_status or DEFAULT_TECHNICIAN_STATUS
        if status not in TECHNICIAN_OPERATIONAL_STATUSES:
            status = DEFAULT_TECHNICIAN_STATUS
        row = TechnicianOperationalStatus(
            tenant_id=tenant_id,
            technician_id=technician_id,
            status=status,
            status_since=now,
            updated_by=actor,
            updated_at=now,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def get(self, tenant_id: UUID, technician_id: UUID) -> dict[str, Any]:
        self._require_technician(tenant_id, technician_id)
        row = self._session.scalar(
            select(TechnicianOperationalStatus).where(
                TechnicianOperationalStatus.tenant_id == tenant_id,
                TechnicianOperationalStatus.technician_id == technician_id,
            )
        )
        if row is None:
            return {
                "technician_id": str(technician_id),
                "status": DEFAULT_TECHNICIAN_STATUS,
                "status_since": None,
                "updated_by": None,
                "updated_at": None,
            }
        return self._serialize(row)

    def transition(
        self,
        tenant_id: UUID,
        technician_id: UUID,
        *,
        to_status: str,
        actor: str,
        reason: str | None = None,
        actor_user_id: UUID | None = None,
        allow_self_only: bool = False,
    ) -> dict[str, Any]:
        try:
            target = normalize_tech_status(to_status)
        except ValueError as exc:
            raise CrmError(
                "invalid_status", f"Unknown technician status: {to_status}"
            ) from exc

        tech = self._require_technician(tenant_id, technician_id)
        if allow_self_only:
            if actor_user_id is None or tech.user_id != actor_user_id:
                raise CrmError(
                    "forbidden",
                    "Technicians may only update their own operational status",
                )

        row = self.ensure_row(tenant_id, technician_id, actor=actor)
        # Re-lock
        row = self._session.scalar(
            select(TechnicianOperationalStatus)
            .where(TechnicianOperationalStatus.id == row.id)
            .with_for_update()
        )
        assert row is not None
        current = row.status
        if current == target:
            return self._serialize(row)
        if (current, target) not in VALID_TECH_STATUS_TRANSITIONS:
            raise CrmError(
                "status_transition_invalid",
                f"Cannot move technician status from {current} to {target}",
            )

        now = datetime.now(UTC)
        # Close open history interval if present (latest without ended_at).
        open_hist = self._session.scalar(
            select(TechnicianStatusHistory)
            .where(
                TechnicianStatusHistory.tenant_id == tenant_id,
                TechnicianStatusHistory.technician_id == technician_id,
                TechnicianStatusHistory.ended_at.is_(None),
            )
            .order_by(TechnicianStatusHistory.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        if open_hist is not None:
            open_hist.ended_at = now

        hist = TechnicianStatusHistory(
            tenant_id=tenant_id,
            technician_id=technician_id,
            old_status=current,
            new_status=target,
            started_at=now,
            ended_at=None,
            changed_by=actor,
            reason=(reason.strip() if reason and reason.strip() else None),
        )
        self._session.add(hist)
        row.status = target
        row.status_since = now
        row.updated_by = actor
        row.updated_at = now
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="technician_status_changed",
            resource_ids={
                "technician_id": str(technician_id),
                "old_status": current,
                "new_status": target,
            },
        )
        emit_dispatch_event(
            self._session,
            tenant_id=tenant_id,
            event_type=DISPATCH_EVENT_TECHNICIAN_STATUS_CHANGED,
            payload={
                "technician_id": str(technician_id),
                "old_status": current,
                "new_status": target,
            },
        )
        return self._serialize(row)

    def history(
        self, tenant_id: UUID, technician_id: UUID, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        self._require_technician(tenant_id, technician_id)
        rows = list(
            self._session.scalars(
                select(TechnicianStatusHistory)
                .where(
                    TechnicianStatusHistory.tenant_id == tenant_id,
                    TechnicianStatusHistory.technician_id == technician_id,
                )
                .order_by(TechnicianStatusHistory.created_at.desc())
                .limit(min(max(limit, 1), 500))
            ).all()
        )
        return [
            {
                "id": str(r.id),
                "old_status": r.old_status,
                "new_status": r.new_status,
                "started_at": r.started_at.isoformat() if r.started_at else None,
                "ended_at": r.ended_at.isoformat() if r.ended_at else None,
                "changed_by": r.changed_by,
                "reason": r.reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    @staticmethod
    def _serialize(row: TechnicianOperationalStatus) -> dict[str, Any]:
        return {
            "technician_id": str(row.technician_id),
            "status": row.status,
            "status_since": row.status_since.isoformat() if row.status_since else None,
            "updated_by": row.updated_by,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
