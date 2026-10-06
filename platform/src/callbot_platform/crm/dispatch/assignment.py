"""Dispatch-aware job assignment over the existing Job model (Phase 12)."""

from __future__ import annotations

import hashlib
import json
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.crm.dispatch.constants import (
    DISPATCH_EVENT_ETA_CHANGED,
    DISPATCH_EVENT_JOB_ASSIGNED,
    DISPATCH_EVENT_JOB_REASSIGNED,
    DISPATCH_EVENT_JOB_UNASSIGNED,
)
from callbot_platform.crm.dispatch.eligibility import AssignmentEligibility
from callbot_platform.crm.dispatch.events import emit_dispatch_event
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs.constants import ASSIGNABLE_STATUSES, TERMINAL_STATUSES
from callbot_platform.crm.jobs.serialize import serialize_job
from callbot_platform.db.models.dispatch import JobAssignmentHistory
from callbot_platform.db.models.jobs import Job
from callbot_platform.telephony.audit import write_audit


def _assign_fingerprint(
    job_id: UUID, technician_id: UUID | None, reason: str | None
) -> str:
    payload = {
        "job_id": str(job_id),
        "technician_id": str(technician_id) if technician_id else None,
        "reason": (reason or "").strip() or None,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


class DispatchAssignmentService:
    """Authoritative assign / unassign / reassign with history + eligibility."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._eligibility = AssignmentEligibility(session)

    def assign(
        self,
        tenant_id: UUID,
        job_id: UUID,
        *,
        technician_id: UUID | None,
        actor: str,
        reason: str | None = None,
        idempotency_key: str | None = None,
        eta: datetime | None = None,
        eta_source: str | None = None,
        skip_eligibility: bool = False,
    ) -> dict[str, Any]:
        key = idempotency_key.strip() if idempotency_key else None
        req_hash = _assign_fingerprint(job_id, technician_id, reason)

        if key:
            existing = self._session.scalar(
                select(JobAssignmentHistory).where(
                    JobAssignmentHistory.tenant_id == tenant_id,
                    JobAssignmentHistory.idempotency_key == key,
                )
            )
            if existing is not None:
                if (
                    existing.idempotency_request_hash
                    and existing.idempotency_request_hash != req_hash
                ):
                    raise CrmError(
                        "idempotency_conflict",
                        "Idempotency-Key reused with a different assignment payload",
                    )
                job = self._session.scalar(
                    select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
                )
                if job is None:
                    raise CrmError("not_found", "Job not found for tenant")
                return serialize_job(job)

        job = self._session.scalar(
            select(Job)
            .where(Job.id == job_id, Job.tenant_id == tenant_id)
            .with_for_update()
        )
        if job is None:
            raise CrmError("not_found", "Job not found for tenant")
        if job.archived_at is not None:
            raise CrmError("job_archived", "Job is archived")
        if job.status in TERMINAL_STATUSES or job.status not in ASSIGNABLE_STATUSES:
            # Preserve Jobs Phase 10 error code for clients/tests.
            raise CrmError(
                "invalid_transition",
                f"Cannot assign/unassign technician while job is {job.status}",
            )

        prev = job.assigned_technician_id
        now = datetime.now(UTC)

        if technician_id is None:
            if prev is None:
                return serialize_job(job)
            # Close open assignment history interval for previous tech.
            self._close_open_assignment(tenant_id, job.id, now)
            job.assigned_technician_id = None
            job.assigned_at = None
            job.assigned_by = None
            action = "job_unassigned"
            event_type = DISPATCH_EVENT_JOB_UNASSIGNED
        else:
            if not skip_eligibility:
                self._eligibility.assert_assignable(tenant_id, job, technician_id)
            if prev == technician_id:
                # Natural idempotency when already assigned to the same tech.
                # Do not insert another history row (would collide on idempotency_key).
                return serialize_job(job)
            self._close_open_assignment(tenant_id, job.id, now)
            job.assigned_technician_id = technician_id
            job.assigned_at = now
            job.assigned_by = actor
            action = "job_reassigned" if prev else "job_assigned"
            event_type = (
                DISPATCH_EVENT_JOB_REASSIGNED if prev else DISPATCH_EVENT_JOB_ASSIGNED
            )

        if eta is not None:
            job.eta = eta if eta.tzinfo else eta.replace(tzinfo=UTC)
            job.eta_source = (eta_source or "MANUAL").strip().upper()
            job.eta_updated_at = now
            emit_dispatch_event(
                self._session,
                tenant_id=tenant_id,
                event_type=DISPATCH_EVENT_ETA_CHANGED,
                payload={"job_id": str(job.id), "eta": job.eta.isoformat()},
            )
        elif technician_id is not None and job.scheduled_starts_at is not None:
            # Derived schedule ETA when none supplied.
            job.eta = job.scheduled_starts_at
            job.eta_source = "SCHEDULE"
            job.eta_updated_at = now

        job.updated_by = actor
        job.updated_at = now
        self._session.flush()

        try:
            with self._session.begin_nested():
                self._record_history(
                    tenant_id,
                    job.id,
                    previous_technician_id=prev,
                    technician_id=technician_id,
                    actor=actor,
                    reason=reason,
                    assigned_at=now,
                    unassigned_at=now if technician_id is None else None,
                    idempotency_key=key,
                    idempotency_request_hash=req_hash if key else None,
                )
        except IntegrityError as exc:
            raced = (
                self._session.scalar(
                    select(JobAssignmentHistory).where(
                        JobAssignmentHistory.tenant_id == tenant_id,
                        JobAssignmentHistory.idempotency_key == key,
                    )
                )
                if key
                else None
            )
            if raced is not None and raced.idempotency_request_hash == req_hash:
                return serialize_job(job)
            raise CrmError(
                "idempotency_conflict",
                "Idempotency-Key conflict on assignment",
            ) from exc

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            resource_ids={
                "job_id": str(job.id),
                "technician_id": str(technician_id) if technician_id else None,
                "previous_technician_id": str(prev) if prev else None,
            },
            payload_summary={"reason": reason} if reason else None,
        )
        emit_dispatch_event(
            self._session,
            tenant_id=tenant_id,
            event_type=event_type,
            payload={
                "job_id": str(job.id),
                "technician_id": str(technician_id) if technician_id else None,
                "previous_technician_id": str(prev) if prev else None,
            },
        )
        # Reload relationships for serialize
        job = self._session.scalar(
            select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
        )
        assert job is not None
        return serialize_job(job)

    def history(
        self, tenant_id: UUID, job_id: UUID, *, limit: int = 100
    ) -> list[dict[str, Any]]:
        job = self._session.scalar(
            select(Job.id).where(Job.id == job_id, Job.tenant_id == tenant_id)
        )
        if job is None:
            raise CrmError("not_found", "Job not found for tenant")
        rows = list(
            self._session.scalars(
                select(JobAssignmentHistory)
                .where(
                    JobAssignmentHistory.tenant_id == tenant_id,
                    JobAssignmentHistory.job_id == job_id,
                )
                .order_by(JobAssignmentHistory.created_at.desc())
                .limit(min(max(limit, 1), 500))
            ).all()
        )
        return [
            {
                "id": str(r.id),
                "previous_technician_id": (
                    str(r.previous_technician_id) if r.previous_technician_id else None
                ),
                "technician_id": str(r.technician_id) if r.technician_id else None,
                "assigned_at": r.assigned_at.isoformat() if r.assigned_at else None,
                "unassigned_at": (
                    r.unassigned_at.isoformat() if r.unassigned_at else None
                ),
                "changed_by": r.changed_by,
                "reason": r.reason,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ]

    def _close_open_assignment(
        self, tenant_id: UUID, job_id: UUID, at: datetime
    ) -> None:
        open_row = self._session.scalar(
            select(JobAssignmentHistory)
            .where(
                JobAssignmentHistory.tenant_id == tenant_id,
                JobAssignmentHistory.job_id == job_id,
                JobAssignmentHistory.technician_id.is_not(None),
                JobAssignmentHistory.unassigned_at.is_(None),
            )
            .order_by(JobAssignmentHistory.created_at.desc())
            .limit(1)
            .with_for_update()
        )
        if open_row is not None:
            open_row.unassigned_at = at

    def _record_history(
        self,
        tenant_id: UUID,
        job_id: UUID,
        *,
        previous_technician_id: UUID | None,
        technician_id: UUID | None,
        actor: str,
        reason: str | None,
        assigned_at: datetime,
        unassigned_at: datetime | None = None,
        idempotency_key: str | None = None,
        idempotency_request_hash: str | None = None,
    ) -> None:
        self._session.add(
            JobAssignmentHistory(
                tenant_id=tenant_id,
                job_id=job_id,
                previous_technician_id=previous_technician_id,
                technician_id=technician_id,
                assigned_at=assigned_at,
                unassigned_at=unassigned_at,
                changed_by=actor,
                reason=(reason.strip() if reason and reason.strip() else None),
                idempotency_key=idempotency_key,
                idempotency_request_hash=idempotency_request_hash,
            )
        )
        self._session.flush()
