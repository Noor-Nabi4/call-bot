"""Job CRM service facade (Phase 10)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs.constants import (
    DEFAULT_CHECKLIST,
    DESCRIPTION_MAX_LEN,
    EDITABLE_STATUSES,
    JobStatus,
    job_ref,
    normalize_priority,
    normalize_status,
)
from callbot_platform.crm.jobs.fingerprint import job_create_fingerprint
from callbot_platform.crm.jobs.numbering import allocate_job_number
from callbot_platform.crm.jobs.search import JobSearchService
from callbot_platform.crm.jobs.serialize import serialize_job
from callbot_platform.crm.jobs.transitions import JobTransitionService
from callbot_platform.db.models import Customer, CustomerLocation
from callbot_platform.db.models.jobs import Job, JobNote, JobStatusHistory, Technician
from callbot_platform.db.models.services.service import Service
from callbot_platform.telephony.audit import write_audit


class JobService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self.search = JobSearchService(session)
        self.transitions = JobTransitionService(session)

    def _load(
        self,
        tenant_id: UUID,
        job_id: UUID,
        *,
        for_update: bool = False,
        require_active: bool = False,
        include_notes: bool = False,
        include_history: bool = False,
        include_attachments: bool = False,
    ) -> Job:
        q = select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
        if for_update:
            q = q.with_for_update()
        opts = [
            selectinload(Job.customer),
            selectinload(Job.assigned_technician),
            selectinload(Job.location),
            selectinload(Job.service),
        ]
        if include_notes:
            opts.append(selectinload(Job.notes).selectinload(JobNote.author))
        if include_history:
            opts.append(selectinload(Job.status_history))
        if include_attachments:
            opts.append(selectinload(Job.attachments))
        q = q.options(*opts)
        job = self._session.scalar(q)
        if job is None:
            raise CrmError("not_found", "Job not found for tenant")
        if require_active and job.archived_at is not None:
            raise CrmError("job_archived", "Job is archived")
        return job

    def _require_customer(self, tenant_id: UUID, customer_id: UUID) -> Customer:
        row = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("customer_not_found", "Customer not found for tenant")
        return row

    def _require_location(
        self, tenant_id: UUID, customer_id: UUID, location_id: UUID
    ) -> CustomerLocation:
        row = self._session.scalar(
            select(CustomerLocation).where(
                CustomerLocation.id == location_id,
                CustomerLocation.tenant_id == tenant_id,
            )
        )
        if row is None or row.archived_at is not None:
            raise CrmError("location_not_found", "Location not found for tenant")
        if row.customer_id != customer_id:
            raise CrmError(
                "location_customer_mismatch",
                "Location does not belong to the job customer",
            )
        return row

    def _require_service(self, tenant_id: UUID, service_id: UUID) -> Service:
        row = self._session.scalar(
            select(Service).where(
                Service.id == service_id, Service.tenant_id == tenant_id
            )
        )
        if row is None or row.archived_at is not None:
            raise CrmError("service_not_found", "Service not found for tenant")
        return row

    def _require_technician(self, tenant_id: UUID, technician_id: UUID) -> Technician:
        row = self._session.scalar(
            select(Technician).where(
                Technician.id == technician_id, Technician.tenant_id == tenant_id
            )
        )
        if row is None or not row.is_active:
            raise CrmError("technician_not_found", "Technician not found for tenant")
        return row

    def _require_equipment(
        self,
        tenant_id: UUID,
        customer_id: UUID,
        equipment_id: UUID,
        *,
        location_id: UUID | None = None,
    ):
        from callbot_platform.crm.equipment.constants import SELECTABLE_STATUSES
        from callbot_platform.db.models.equipment import Equipment

        row = self._session.scalar(
            select(Equipment).where(
                Equipment.id == equipment_id, Equipment.tenant_id == tenant_id
            )
        )
        if row is None or row.archived_at is not None:
            raise CrmError("equipment_not_found", "Equipment not found for tenant")
        if row.customer_id != customer_id:
            raise CrmError(
                "equipment_customer_mismatch",
                "Equipment does not belong to the job customer",
            )
        if row.status not in SELECTABLE_STATUSES:
            raise CrmError(
                "equipment_not_selectable",
                "Equipment is not available for job association",
            )
        if (
            location_id is not None
            and row.location_id is not None
            and row.location_id != location_id
        ):
            raise CrmError(
                "equipment_location_mismatch",
                "Equipment location does not match job location",
            )
        return row

    def _validate_schedule(
        self,
        starts: datetime | None,
        ends: datetime | None,
    ) -> None:
        if starts is not None and ends is not None and ends <= starts:
            raise CrmError(
                "invalid_schedule",
                "scheduled_ends_at must be after scheduled_starts_at",
            )

    def get(self, tenant_id: UUID, job_id: UUID) -> dict[str, Any]:
        job = self._load(
            tenant_id,
            job_id,
            include_notes=True,
            include_history=True,
            include_attachments=True,
        )
        return serialize_job(
            job,
            include_notes=True,
            include_history=True,
            include_attachments=True,
        )

    def list(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.search.search(tenant_id, **kwargs)

    def create(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        actor: str,
        service_type: str | None = None,
        service_id: UUID | None = None,
        location_id: UUID | None = None,
        equipment_id: UUID | None = None,
        description: str | None = None,
        priority: str | None = None,
        technician_id: UUID | None = None,
        scheduled_starts_at: datetime | None = None,
        scheduled_ends_at: datetime | None = None,
        appointment_id: UUID | None = None,
        lead_id: UUID | None = None,
        call_id: UUID | None = None,
        status: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        key = idempotency_key.strip() if idempotency_key else None

        customer = self._require_customer(tenant_id, customer_id)
        svc = None
        if service_id is not None:
            svc = self._require_service(tenant_id, service_id)
        stype = (service_type or "").strip()
        if svc is not None:
            stype = stype or svc.name
        if not stype:
            raise CrmError("service_required", "service_type or service_id is required")
        stype = stype[:128]

        if location_id is not None:
            self._require_location(tenant_id, customer.id, location_id)
        if equipment_id is not None:
            self._require_equipment(
                tenant_id,
                customer.id,
                equipment_id,
                location_id=location_id,
            )

        tech_id = None
        if technician_id is not None:
            self._require_technician(tenant_id, technician_id)
            tech_id = technician_id

        try:
            prio = normalize_priority(priority)
        except ValueError as exc:
            raise CrmError("invalid_priority", str(exc)) from exc

        initial = JobStatus.NEW.value
        if status:
            try:
                initial = normalize_status(status)
            except ValueError as exc:
                raise CrmError("invalid_status", str(exc)) from exc
            if initial not in {JobStatus.NEW.value, JobStatus.SCHEDULED.value}:
                raise CrmError(
                    "invalid_status",
                    "Jobs may only be created as NEW or SCHEDULED",
                )

        desc = None
        if description is not None:
            desc = description.strip() or None
            if desc and len(desc) > DESCRIPTION_MAX_LEN:
                raise CrmError("invalid_description", "description is too long")

        self._validate_schedule(scheduled_starts_at, scheduled_ends_at)

        req_hash = job_create_fingerprint(
            customer_id=customer.id,
            service_id=service_id,
            service_type=stype,
            location_id=location_id,
            equipment_id=equipment_id,
            description=desc,
            priority=prio,
            technician_id=tech_id,
            scheduled_starts_at=scheduled_starts_at,
            scheduled_ends_at=scheduled_ends_at,
            appointment_id=appointment_id,
            lead_id=lead_id,
            call_id=call_id,
            status=initial,
        )

        if key:
            existing = self._session.scalar(
                select(Job).where(
                    Job.tenant_id == tenant_id, Job.idempotency_key == key
                )
            )
            if existing is not None:
                if (
                    existing.idempotency_request_hash
                    and existing.idempotency_request_hash != req_hash
                ):
                    raise CrmError(
                        "idempotency_conflict",
                        "Idempotency-Key reused with a different job payload",
                    )
                return self.get(tenant_id, existing.id)

        number = allocate_job_number(self._session, tenant_id)
        ref = job_ref()
        try:
            with self._session.begin_nested():
                job = Job(
                    tenant_id=tenant_id,
                    job_number=number,
                    customer_id=customer.id,
                    location_id=location_id,
                    equipment_id=equipment_id,
                    service_id=service_id,
                    appointment_id=appointment_id,
                    lead_id=lead_id,
                    call_id=call_id,
                    assigned_technician_id=None,
                    status=initial,
                    priority=prio,
                    service_type=stype,
                    description=desc,
                    scheduled_starts_at=scheduled_starts_at,
                    scheduled_ends_at=scheduled_ends_at,
                    checklist=[dict(item) for item in DEFAULT_CHECKLIST],
                    reference_code=ref,
                    idempotency_key=key,
                    idempotency_request_hash=req_hash if key else None,
                    created_by=actor,
                    updated_by=actor,
                )
                self._session.add(job)
                self._session.flush()
        except IntegrityError as exc:
            if key:
                raced = self._session.scalar(
                    select(Job).where(
                        Job.tenant_id == tenant_id, Job.idempotency_key == key
                    )
                )
                if raced is not None:
                    if (
                        raced.idempotency_request_hash
                        and raced.idempotency_request_hash != req_hash
                    ):
                        raise CrmError(
                            "idempotency_conflict",
                            "Idempotency-Key reused with a different job payload",
                        ) from exc
                    return self.get(tenant_id, raced.id)
            raise CrmError("job_conflict", "Conflicting job create") from exc

        self._session.add(
            JobStatusHistory(
                tenant_id=tenant_id,
                job_id=job.id,
                from_status=None,
                to_status=initial,
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
            },
        )
        # Initial technician on create goes through the same assignment service
        # so history, audit, eligibility, and dispatch_events stay consistent.
        if tech_id is not None:
            from callbot_platform.crm.dispatch.assignment import (
                DispatchAssignmentService,
            )

            return DispatchAssignmentService(self._session).assign(
                tenant_id,
                job.id,
                technician_id=tech_id,
                actor=actor,
                reason="created_with_technician",
            )
        return self.get(tenant_id, job.id)

    def update(
        self,
        tenant_id: UUID,
        job_id: UUID,
        *,
        actor: str,
        description: str | None = None,
        clear_description: bool = False,
        priority: str | None = None,
        location_id: UUID | None = None,
        clear_location: bool = False,
        equipment_id: UUID | None = None,
        clear_equipment: bool = False,
        service_id: UUID | None = None,
        clear_service: bool = False,
        service_type: str | None = None,
        scheduled_starts_at: datetime | None = None,
        scheduled_ends_at: datetime | None = None,
        clear_schedule: bool = False,
        status: str | None = None,
    ) -> dict[str, Any]:
        if status is not None:
            raise CrmError(
                "use_transition",
                "Use POST /jobs/{id}/transition to change status",
            )
        job = self._load(tenant_id, job_id, for_update=True, require_active=True)

        mutating_fields = any(
            [
                clear_description,
                description is not None,
                priority is not None,
                clear_location,
                location_id is not None,
                clear_equipment,
                equipment_id is not None,
                clear_service,
                service_id is not None,
                service_type is not None,
                clear_schedule,
                scheduled_starts_at is not None,
                scheduled_ends_at is not None,
            ]
        )
        if mutating_fields and job.status not in EDITABLE_STATUSES:
            raise CrmError(
                "job_immutable",
                "Job fields are immutable after CONFIRMED; use transition/assign APIs",
            )

        if clear_description:
            job.description = None
        elif description is not None:
            desc = description.strip() or None
            if desc and len(desc) > DESCRIPTION_MAX_LEN:
                raise CrmError("invalid_description", "description is too long")
            job.description = desc

        if priority is not None:
            try:
                job.priority = normalize_priority(priority)
            except ValueError as exc:
                raise CrmError("invalid_priority", str(exc)) from exc

        if clear_location:
            job.location_id = None
        elif location_id is not None:
            self._require_location(tenant_id, job.customer_id, location_id)
            job.location_id = location_id

        if clear_equipment:
            job.equipment_id = None
        elif equipment_id is not None:
            self._require_equipment(
                tenant_id,
                job.customer_id,
                equipment_id,
                location_id=job.location_id,
            )
            job.equipment_id = equipment_id

        if clear_service:
            job.service_id = None
        elif service_id is not None:
            svc = self._require_service(tenant_id, service_id)
            job.service_id = service_id
            if not service_type:
                job.service_type = svc.name[:128]

        if service_type is not None and service_type.strip():
            job.service_type = service_type.strip()[:128]

        if clear_schedule:
            job.scheduled_starts_at = None
            job.scheduled_ends_at = None
        else:
            starts = (
                scheduled_starts_at
                if scheduled_starts_at is not None
                else job.scheduled_starts_at
            )
            ends = (
                scheduled_ends_at
                if scheduled_ends_at is not None
                else job.scheduled_ends_at
            )
            if scheduled_starts_at is not None:
                job.scheduled_starts_at = scheduled_starts_at
            if scheduled_ends_at is not None:
                job.scheduled_ends_at = scheduled_ends_at
            self._validate_schedule(starts, ends)

        job.updated_by = actor
        job.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_updated",
            resource_ids={"job_id": str(job.id), "job_number": job.job_number},
        )
        return self.get(tenant_id, job_id)

    def assign(
        self,
        tenant_id: UUID,
        job_id: UUID,
        *,
        technician_id: UUID | None,
        actor: str,
        reason: str | None = None,
        idempotency_key: str | None = None,
        skip_eligibility: bool = False,
    ) -> dict[str, Any]:
        """Assign via DispatchAssignmentService (history + eligibility + events)."""
        from callbot_platform.crm.dispatch.assignment import DispatchAssignmentService

        return DispatchAssignmentService(self._session).assign(
            tenant_id,
            job_id,
            technician_id=technician_id,
            actor=actor,
            reason=reason,
            idempotency_key=idempotency_key,
            skip_eligibility=skip_eligibility,
        )

    def transition(
        self, tenant_id: UUID, job_id: UUID, **kwargs: Any
    ) -> dict[str, Any]:
        return self.transitions.transition(tenant_id, job_id, **kwargs)

    def history(self, tenant_id: UUID, job_id: UUID) -> list[dict[str, Any]]:
        return self.transitions.history(tenant_id, job_id)

    def archive(self, tenant_id: UUID, job_id: UUID, *, actor: str) -> dict[str, Any]:
        job = self._load(tenant_id, job_id, for_update=True)
        if job.archived_at is not None:
            return self.get(tenant_id, job_id)
        if job.status not in {
            JobStatus.NEW.value,
            JobStatus.COMPLETED.value,
            JobStatus.CANCELLED.value,
            JobStatus.NO_SHOW.value,
        }:
            raise CrmError(
                "archive_not_allowed",
                "Only NEW, COMPLETED, CANCELLED, or NO_SHOW jobs can be archived",
            )
        job.archived_at = datetime.now(UTC)
        job.updated_by = actor
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_archived",
            resource_ids={"job_id": str(job.id)},
        )
        return self.get(tenant_id, job_id)

    def restore(self, tenant_id: UUID, job_id: UUID, *, actor: str) -> dict[str, Any]:
        job = self._load(tenant_id, job_id, for_update=True)
        if job.archived_at is None:
            return self.get(tenant_id, job_id)
        job.archived_at = None
        job.updated_by = actor
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="job_restored",
            resource_ids={"job_id": str(job.id)},
        )
        return self.get(tenant_id, job_id)
