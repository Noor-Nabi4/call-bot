"""Job repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.jobs.numbering import allocate_job_number
from callbot_platform.crm.jobs.transitions import JobTransitionService
from callbot_platform.db.models import (
    Appointment,
    Customer,
    Job,
    JobNote,
    JobStatusHistory,
    Technician,
)
from callbot_platform.jobs.errors import (
    ASSIGNABLE_STATUSES,
    DEFAULT_CHECKLIST,
    JobsError,
    checklist_item_id,
    coerce_status,
    job_ref,
)
from callbot_platform.telephony.audit import write_audit


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._transitions = JobTransitionService(session)

    def create_from_appointment(
        self, appointment: Appointment
    ) -> dict[str, Any] | None:
        existing = self._session.scalar(
            select(Job).where(
                Job.tenant_id == appointment.tenant_id,
                Job.appointment_id == appointment.id,
            )
        )
        if existing is not None:
            return self._serialize(existing)
        number = allocate_job_number(self._session, appointment.tenant_id)
        job = Job(
            tenant_id=appointment.tenant_id,
            job_number=number,
            customer_id=appointment.customer_id,
            appointment_id=appointment.id,
            lead_id=appointment.lead_id,
            call_id=appointment.call_id,
            status="SCHEDULED",
            priority="MEDIUM",
            service_type=appointment.service_type,
            scheduled_starts_at=appointment.starts_at,
            scheduled_ends_at=appointment.ends_at,
            checklist=[dict(item) for item in DEFAULT_CHECKLIST],
            reference_code=job_ref(),
            created_by="voice-agent",
            updated_by="voice-agent",
        )
        self._session.add(job)
        self._session.flush()
        self._session.add(
            JobStatusHistory(
                tenant_id=appointment.tenant_id,
                job_id=job.id,
                from_status=None,
                to_status="SCHEDULED",
                changed_by="voice-agent",
                reason="created_from_appointment",
            )
        )
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=appointment.tenant_id,
            actor="voice-agent",
            action="job_created_from_appointment",
            resource_ids={
                "job_id": str(job.id),
                "appointment_id": str(appointment.id),
                "job_number": job.job_number,
                "reference_code": job.reference_code,
            },
        )
        return self._serialize(job)

    def create(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        service_type: str,
        status: str = "NEW",
        scheduled_starts_at: datetime | None = None,
        scheduled_ends_at: datetime | None = None,
        appointment_id: UUID | None = None,
        lead_id: UUID | None = None,
        call_id: UUID | None = None,
        actor: str = "dispatcher",
    ) -> dict[str, Any]:
        status = coerce_status(status)
        if status not in {"NEW", "SCHEDULED"}:
            raise JobsError(
                "invalid_status", "Jobs may only be created as NEW or SCHEDULED"
            )
        customer = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        )
        if customer is None:
            raise JobsError("customer_not_found", "Customer not found for tenant")
        if not service_type or not service_type.strip():
            raise JobsError("invalid_service_type", "service_type is required")
        number = allocate_job_number(self._session, tenant_id)
        job = Job(
            tenant_id=tenant_id,
            job_number=number,
            customer_id=customer_id,
            appointment_id=appointment_id,
            lead_id=lead_id,
            call_id=call_id,
            status=status,
            priority="MEDIUM",
            service_type=service_type.strip(),
            scheduled_starts_at=scheduled_starts_at,
            scheduled_ends_at=scheduled_ends_at,
            checklist=[dict(item) for item in DEFAULT_CHECKLIST],
            reference_code=job_ref(),
            created_by=actor,
            updated_by=actor,
        )
        self._session.add(job)
        self._session.flush()
        self._session.add(
            JobStatusHistory(
                tenant_id=tenant_id,
                job_id=job.id,
                from_status=None,
                to_status=status,
                changed_by=actor,
                reason="created",
            )
        )
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_created",
            resource_ids={
                "job_id": str(job.id),
                "job_number": job.job_number,
                "reference_code": job.reference_code,
            },
        )
        return self._serialize(job)

    def list(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        technician_id: UUID | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        q = (
            select(Job)
            .where(Job.tenant_id == tenant_id)
            .options(
                selectinload(Job.customer),
                selectinload(Job.assigned_technician),
                selectinload(Job.notes),
            )
            .order_by(Job.scheduled_starts_at.asc().nullslast(), Job.created_at.desc())
            .limit(max(1, min(limit, 200)))
        )
        if status:
            q = q.where(Job.status == coerce_status(status))
        if technician_id:
            q = q.where(Job.assigned_technician_id == technician_id)
        return [self._serialize(j) for j in self._session.scalars(q).all()]

    def get(self, tenant_id: UUID, job_id: UUID) -> dict[str, Any] | None:
        job = self._session.scalar(
            select(Job)
            .where(Job.id == job_id, Job.tenant_id == tenant_id)
            .options(
                selectinload(Job.customer),
                selectinload(Job.assigned_technician),
                selectinload(Job.notes).selectinload(JobNote.author),
            )
        )
        if job is None:
            return None
        return self._serialize(job, include_notes=True)

    def assign(
        self,
        tenant_id: UUID,
        job_id: UUID,
        *,
        technician_id: UUID,
        actor: str = "dispatcher",
    ) -> dict[str, Any]:
        job = self._session.scalar(
            select(Job)
            .where(Job.id == job_id, Job.tenant_id == tenant_id)
            .with_for_update()
        )
        if job is None:
            raise JobsError("job_not_found", "Job not found for tenant")
        if job.archived_at is not None:
            raise JobsError("job_archived", "Cannot assign an archived job")
        if job.status not in ASSIGNABLE_STATUSES:
            raise JobsError(
                "invalid_transition",
                f"Cannot assign technician while job is {job.status}",
            )
        tech = self._session.scalar(
            select(Technician).where(
                Technician.id == technician_id, Technician.tenant_id == tenant_id
            )
        )
        if tech is None or not tech.is_active:
            raise JobsError("technician_not_found", "Technician not found")
        job.assigned_technician_id = technician_id
        job.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_assigned",
            resource_ids={
                "job_id": str(job.id),
                "technician_id": str(technician_id),
            },
        )
        return self.get(tenant_id, job_id) or self._serialize(job)

    def transition(
        self,
        tenant_id: UUID,
        job_id: UUID,
        *,
        status: str,
        completion_notes: str | None = None,
        actor_user_id: UUID | None = None,
        actor: str = "dispatcher",
    ) -> dict[str, Any]:
        from callbot_platform.crm.errors import CrmError

        try:
            result = self._transitions.transition(
                tenant_id,
                job_id,
                to_status=status,
                actor=actor,
                completion_notes=completion_notes,
                actor_user_id=actor_user_id,
            )
        except CrmError as exc:
            raise JobsError(exc.code, str(exc)) from exc
        # Preserve legacy serialisation shape for ops clients.
        return self.get(tenant_id, job_id) or result

    def update_checklist(
        self,
        tenant_id: UUID,
        job_id: UUID,
        *,
        checklist: list[dict[str, Any]],
        actor: str = "technician",
    ) -> dict[str, Any]:
        job = self._get(tenant_id, job_id)
        cleaned: list[dict[str, Any]] = []
        for item in checklist:
            cleaned.append(
                {
                    "id": str(item.get("id") or checklist_item_id()),
                    "label": str(item.get("label") or "").strip() or "Item",
                    "done": bool(item.get("done")),
                }
            )
        job.checklist = cleaned
        job.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_checklist_updated",
            resource_ids={"job_id": str(job.id)},
        )
        return self.get(tenant_id, job_id) or self._serialize(job)

    def add_note(
        self,
        tenant_id: UUID,
        job_id: UUID,
        *,
        body: str,
        author_user_id: UUID | None,
        actor: str = "technician",
    ) -> dict[str, Any]:
        if not body or not body.strip():
            raise JobsError("invalid_note", "Note body is required")
        job = self._get(tenant_id, job_id)
        note = JobNote(
            tenant_id=tenant_id,
            job_id=job.id,
            author_user_id=author_user_id,
            body=body.strip(),
        )
        self._session.add(note)
        job.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_note_added",
            resource_ids={"job_id": str(job.id), "note_id": str(note.id)},
        )
        return self.get(tenant_id, job_id) or self._serialize(job)

    def _get(self, tenant_id: UUID, job_id: UUID) -> Job:
        job = self._session.scalar(
            select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
        )
        if job is None:
            raise JobsError("job_not_found", "Job not found for tenant")
        return job

    def _serialize(self, job: Job, *, include_notes: bool = False) -> dict[str, Any]:
        customer = None
        if job.customer is not None:
            customer = {
                "id": str(job.customer.id),
                "name": job.customer.name,
                "email": job.customer.email,
                "address": job.customer.address,
            }
        tech = None
        if job.assigned_technician is not None:
            tech = {
                "id": str(job.assigned_technician.id),
                "display_name": job.assigned_technician.display_name,
            }
        data: dict[str, Any] = {
            "id": str(job.id),
            "tenant_id": str(job.tenant_id),
            "job_number": job.job_number,
            "customer_id": str(job.customer_id),
            "customer": customer,
            "appointment_id": str(job.appointment_id) if job.appointment_id else None,
            "lead_id": str(job.lead_id) if job.lead_id else None,
            "call_id": str(job.call_id) if job.call_id else None,
            "assigned_technician_id": (
                str(job.assigned_technician_id) if job.assigned_technician_id else None
            ),
            "assigned_technician": tech,
            "status": job.status,
            "priority": job.priority,
            "description": job.description,
            "location_id": str(job.location_id) if job.location_id else None,
            "service_id": str(job.service_id) if job.service_id else None,
            "service_type": job.service_type,
            "scheduled_starts_at": (
                job.scheduled_starts_at.isoformat() if job.scheduled_starts_at else None
            ),
            "scheduled_ends_at": (
                job.scheduled_ends_at.isoformat() if job.scheduled_ends_at else None
            ),
            "checklist": job.checklist or [],
            "completion_notes": job.completion_notes,
            "reference_code": job.reference_code,
            "archived_at": job.archived_at.isoformat() if job.archived_at else None,
            "created_at": job.created_at.isoformat() if job.created_at else None,
            "updated_at": job.updated_at.isoformat() if job.updated_at else None,
        }
        if include_notes:
            notes_out = []
            for n in job.notes or []:
                notes_out.append(
                    {
                        "id": str(n.id),
                        "body": n.body,
                        "author_user_id": (
                            str(n.author_user_id) if n.author_user_id else None
                        ),
                        "author_name": n.author.name if n.author else None,
                        "created_at": n.created_at.isoformat()
                        if n.created_at
                        else None,
                    }
                )
            data["notes"] = notes_out
        return data
