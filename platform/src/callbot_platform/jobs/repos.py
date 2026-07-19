"""Tenant-scoped jobs and technicians repositories."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.db.models import (
    Appointment,
    Customer,
    Job,
    JobNote,
    Technician,
)
from callbot_platform.security.session import ROLE_TECHNICIAN
from callbot_platform.telephony.audit import write_audit

TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"scheduled", "canceled"}),
    "scheduled": frozenset({"dispatched", "canceled"}),
    "dispatched": frozenset({"in_progress", "scheduled", "canceled"}),
    "in_progress": frozenset({"completed", "canceled"}),
    "completed": frozenset(),
    "canceled": frozenset(),
}

ASSIGNABLE_STATUSES = frozenset({"new", "scheduled", "dispatched"})

DEFAULT_CHECKLIST = [
    {"id": "arrive", "label": "Arrive on site", "done": False},
    {"id": "diagnose", "label": "Diagnose issue", "done": False},
    {"id": "complete_work", "label": "Complete work", "done": False},
    {"id": "customer_signoff", "label": "Customer sign-off", "done": False},
]


class JobsError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _job_ref() -> str:
    return f"JOB-{secrets.token_hex(3).upper()}"


class TechnicianRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(self, tenant_id: UUID, *, active_only: bool = True) -> list[dict[str, Any]]:
        q = select(Technician).where(Technician.tenant_id == tenant_id)
        if active_only:
            q = q.where(Technician.is_active.is_(True))
        rows = self._session.scalars(q.order_by(Technician.display_name)).all()
        return [self._serialize(r) for r in rows]

    def create(
        self,
        tenant_id: UUID,
        *,
        email: str,
        password: str,
        name: str,
        phone: str | None = None,
        actor: str = "dispatcher",
    ) -> dict[str, Any]:
        from callbot_platform.auth.repos import AuthRepository

        user = AuthRepository(self._session).create_user(
            tenant_id,
            email=email,
            password=password,
            name=name,
            role=ROLE_TECHNICIAN,
            phone=phone,
            actor=actor,
        )
        tech_id = user.get("technician_id")
        if not tech_id:
            raise JobsError("tech_create_failed", "Technician profile was not created")
        tech = self._session.get(Technician, UUID(tech_id))
        assert tech is not None
        return self._serialize(tech)

    def update_location(
        self,
        tenant_id: UUID,
        technician_id: UUID,
        *,
        lat: float,
        lng: float,
    ) -> dict[str, Any]:
        tech = self._session.scalar(
            select(Technician).where(
                Technician.id == technician_id, Technician.tenant_id == tenant_id
            )
        )
        if tech is None:
            raise JobsError("technician_not_found", "Technician not found")
        tech.last_lat = lat
        tech.last_lng = lng
        tech.last_location_at = datetime.now(UTC)
        tech.updated_at = datetime.now(UTC)
        self._session.flush()
        return self._serialize(tech)

    def _serialize(self, tech: Technician) -> dict[str, Any]:
        return {
            "id": str(tech.id),
            "tenant_id": str(tech.tenant_id),
            "user_id": str(tech.user_id),
            "display_name": tech.display_name,
            "phone": tech.phone,
            "is_active": tech.is_active,
            "last_lat": tech.last_lat,
            "last_lng": tech.last_lng,
            "last_location_at": (
                tech.last_location_at.isoformat() if tech.last_location_at else None
            ),
        }


class JobRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_from_appointment(self, appointment: Appointment) -> dict[str, Any] | None:
        existing = self._session.scalar(
            select(Job).where(
                Job.tenant_id == appointment.tenant_id,
                Job.appointment_id == appointment.id,
            )
        )
        if existing is not None:
            return self._serialize(existing)
        job = Job(
            tenant_id=appointment.tenant_id,
            customer_id=appointment.customer_id,
            appointment_id=appointment.id,
            lead_id=appointment.lead_id,
            call_id=appointment.call_id,
            status="scheduled",
            service_type=appointment.service_type,
            scheduled_starts_at=appointment.starts_at,
            scheduled_ends_at=appointment.ends_at,
            checklist=[dict(item) for item in DEFAULT_CHECKLIST],
            reference_code=_job_ref(),
        )
        self._session.add(job)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=appointment.tenant_id,
            actor="voice-agent",
            action="job_created_from_appointment",
            resource_ids={
                "job_id": str(job.id),
                "appointment_id": str(appointment.id),
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
        status: str = "new",
        scheduled_starts_at: datetime | None = None,
        scheduled_ends_at: datetime | None = None,
        appointment_id: UUID | None = None,
        lead_id: UUID | None = None,
        call_id: UUID | None = None,
        actor: str = "dispatcher",
    ) -> dict[str, Any]:
        if status not in TRANSITIONS:
            raise JobsError("invalid_status", f"Unknown status: {status}")
        customer = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        )
        if customer is None:
            raise JobsError("customer_not_found", "Customer not found for tenant")
        if not service_type or not service_type.strip():
            raise JobsError("invalid_service_type", "service_type is required")
        job = Job(
            tenant_id=tenant_id,
            customer_id=customer_id,
            appointment_id=appointment_id,
            lead_id=lead_id,
            call_id=call_id,
            status=status,
            service_type=service_type.strip(),
            scheduled_starts_at=scheduled_starts_at,
            scheduled_ends_at=scheduled_ends_at,
            checklist=[dict(item) for item in DEFAULT_CHECKLIST],
            reference_code=_job_ref(),
        )
        self._session.add(job)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_created",
            resource_ids={"job_id": str(job.id), "reference_code": job.reference_code},
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
            q = q.where(Job.status == status)
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
        job = self._get(tenant_id, job_id)
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
        job = self._get(tenant_id, job_id)
        allowed = TRANSITIONS.get(job.status, frozenset())
        if status not in allowed:
            raise JobsError(
                "invalid_transition",
                f"Cannot move job from {job.status} to {status}",
            )
        if status == "dispatched" and job.assigned_technician_id is None:
            raise JobsError(
                "technician_required",
                "Assign a technician before dispatching the job",
            )
        if status == "completed":
            notes = (completion_notes or "").strip()
            if not notes:
                raise JobsError(
                    "completion_notes_required",
                    "Completion notes are required when completing a job",
                )
            job.completion_notes = notes
            note = JobNote(
                tenant_id=tenant_id,
                job_id=job.id,
                author_user_id=actor_user_id,
                body=f"Completed: {notes}",
            )
            self._session.add(note)
        job.status = status
        job.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_status_changed",
            resource_ids={"job_id": str(job.id)},
            payload_summary={"status": status},
        )
        return self.get(tenant_id, job_id) or self._serialize(job)

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
                    "id": str(item.get("id") or secrets.token_hex(4)),
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

    def _serialize(
        self, job: Job, *, include_notes: bool = False
    ) -> dict[str, Any]:
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
                        "created_at": n.created_at.isoformat() if n.created_at else None,
                    }
                )
            data["notes"] = notes_out
        return data
