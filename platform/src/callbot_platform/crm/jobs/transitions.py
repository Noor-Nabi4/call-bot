"""Job status transition policy and service."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs.constants import (
    REQUIRES_TECHNICIAN,
    VALID_TRANSITIONS,
    JobStatus,
    normalize_status,
)
from callbot_platform.crm.jobs.serialize import serialize_job, serialize_status_history
from callbot_platform.db.models.jobs import Job, JobNote, JobStatusHistory
from callbot_platform.telephony.audit import write_audit


class JobTransitionService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def history(self, tenant_id: UUID, job_id: UUID) -> list[dict[str, Any]]:
        job = self._session.scalar(
            select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
        )
        if job is None:
            raise CrmError("not_found", "Job not found for tenant")
        rows = list(
            self._session.scalars(
                select(JobStatusHistory)
                .where(
                    JobStatusHistory.tenant_id == tenant_id,
                    JobStatusHistory.job_id == job_id,
                )
                .order_by(JobStatusHistory.created_at.asc(), JobStatusHistory.id.asc())
            ).all()
        )
        return [serialize_status_history(r) for r in rows]

    def transition(
        self,
        tenant_id: UUID,
        job_id: UUID,
        *,
        to_status: str,
        actor: str,
        reason: str | None = None,
        completion_notes: str | None = None,
        actor_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        try:
            target = normalize_status(to_status)
        except ValueError as exc:
            raise CrmError(
                "invalid_status", f"Unknown job status: {to_status}"
            ) from exc

        job = self._session.scalar(
            select(Job)
            .where(Job.id == job_id, Job.tenant_id == tenant_id)
            .options(
                selectinload(Job.customer),
                selectinload(Job.assigned_technician),
                selectinload(Job.location),
                selectinload(Job.service),
                selectinload(Job.status_history),
                selectinload(Job.notes),
            )
            .with_for_update()
        )
        if job is None:
            raise CrmError("not_found", "Job not found for tenant")
        if job.archived_at is not None:
            raise CrmError("job_archived", "Cannot transition an archived job")

        current = job.status
        if current == target:
            return serialize_job(job, include_notes=True, include_history=True)

        if (current, target) not in VALID_TRANSITIONS:
            raise CrmError(
                "invalid_transition",
                f"Cannot move job from {current} to {target}",
            )

        if target in REQUIRES_TECHNICIAN and job.assigned_technician_id is None:
            raise CrmError(
                "technician_required",
                "Assign a technician before this status transition",
            )

        if target == JobStatus.COMPLETED.value:
            notes = (completion_notes or "").strip()
            if not notes:
                raise CrmError(
                    "completion_notes_required",
                    "Completion notes are required when completing a job",
                )
            job.completion_notes = notes
            job.completed_at = datetime.now(UTC)
            self._session.add(
                JobNote(
                    tenant_id=tenant_id,
                    job_id=job.id,
                    author_user_id=actor_user_id,
                    body=f"Completed: {notes}",
                )
            )

        if target == JobStatus.CANCELLED.value:
            job.cancelled_at = datetime.now(UTC)
        if target == JobStatus.NO_SHOW.value:
            job.cancelled_at = datetime.now(UTC)

        history = JobStatusHistory(
            tenant_id=tenant_id,
            job_id=job.id,
            from_status=current,
            to_status=target,
            changed_by=actor,
            reason=(reason.strip() if reason and reason.strip() else None),
        )
        self._session.add(history)
        job.status = target
        job.updated_by = actor
        job.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_status_changed",
            resource_ids={"job_id": str(job.id), "job_number": job.job_number},
            payload_summary={"from": current, "to": target},
        )
        if target == JobStatus.ARRIVED.value:
            from callbot_platform.automations.publishers import (
                publish_technician_arrived,
            )

            publish_technician_arrived(
                self._session,
                tenant_id=tenant_id,
                job_id=job.id,
                customer_id=job.customer_id,
                technician_id=job.assigned_technician_id,
                job_number=job.job_number,
            )
        if target == JobStatus.COMPLETED.value:
            from callbot_platform.automations.publishers import publish_job_completed

            publish_job_completed(
                self._session,
                tenant_id=tenant_id,
                job_id=job.id,
                customer_id=job.customer_id,
                job_number=job.job_number,
            )
        return serialize_job(job, include_notes=True, include_history=True)
