"""Appointment CRM service facade (Phase 11)."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.appointments.constants import (
    ACTIVE_BOOKING_STATUSES,
    ASSIGNABLE_STATUSES,
    DEFAULT_APPOINTMENT_STATUS,
    DESCRIPTION_MAX_LEN,
    EDITABLE_STATUSES,
    NOTES_MAX_LEN,
    TERMINAL_STATUSES,
    AppointmentStatus,
    appointment_ref,
    normalize_priority,
    normalize_status,
)
from callbot_platform.crm.appointments.fingerprint import appointment_create_fingerprint
from callbot_platform.crm.appointments.numbering import allocate_appointment_number
from callbot_platform.crm.appointments.search import AppointmentSearchService
from callbot_platform.crm.appointments.serialize import serialize_appointment
from callbot_platform.crm.appointments.transitions import AppointmentTransitionService
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import Customer, CustomerLocation
from callbot_platform.db.models.jobs import Job, Technician
from callbot_platform.db.models.scheduling import Appointment, AppointmentStatusHistory
from callbot_platform.db.models.services.service import Service
from callbot_platform.scheduling.errors import ensure_aware
from callbot_platform.scheduling.repos.settings_repo import ScheduleSettingsRepository
from callbot_platform.telephony.audit import write_audit

# Initial statuses allowed on create — mirrors Jobs (NEW/SCHEDULED only).
_CREATABLE_STATUSES = frozenset(
    {
        AppointmentStatus.TENTATIVE.value,
        AppointmentStatus.SCHEDULED.value,
        AppointmentStatus.CONFIRMED.value,
    }
)
# Statuses that may be archived — not actively occupying a technician's calendar.
_ARCHIVABLE_STATUSES = (
    frozenset({AppointmentStatus.TENTATIVE.value}) | TERMINAL_STATUSES
)


class AppointmentService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self.search = AppointmentSearchService(session)
        self.transitions = AppointmentTransitionService(session)
        self._settings = ScheduleSettingsRepository(session)

    # --- loaders / validators ---

    def _load(
        self,
        tenant_id: UUID,
        appointment_id: UUID,
        *,
        for_update: bool = False,
        require_active: bool = False,
        include_history: bool = False,
    ) -> Appointment:
        q = select(Appointment).where(
            Appointment.id == appointment_id, Appointment.tenant_id == tenant_id
        )
        if for_update:
            q = q.with_for_update()
        opts = [
            selectinload(Appointment.customer),
            selectinload(Appointment.assigned_technician),
            selectinload(Appointment.location),
            selectinload(Appointment.service),
        ]
        if include_history:
            opts.append(selectinload(Appointment.status_history))
        q = q.options(*opts)
        appt = self._session.scalar(q)
        if appt is None:
            raise CrmError("not_found", "Appointment not found for tenant")
        if require_active and appt.archived_at is not None:
            raise CrmError("appointment_archived", "Appointment is archived")
        return appt

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
                "Location does not belong to the appointment customer",
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

    def _require_job(self, tenant_id: UUID, job_id: UUID, customer_id: UUID) -> Job:
        row = self._session.scalar(
            select(Job).where(Job.id == job_id, Job.tenant_id == tenant_id)
        )
        if row is None:
            raise CrmError("job_not_found", "Job not found for tenant")
        if row.customer_id != customer_id:
            raise CrmError(
                "job_customer_mismatch",
                "Job does not belong to the appointment customer",
            )
        return row

    def _resolve_duration(
        self,
        tenant_id: UUID,
        *,
        starts: datetime,
        ends_at: datetime | None,
        duration_minutes: int | None,
        service: Service | None,
    ) -> tuple[datetime, int]:
        if ends_at is not None:
            ends = ensure_aware(ends_at)
            if ends <= starts:
                raise CrmError("invalid_schedule", "ends_at must be after starts_at")
            minutes = int((ends - starts).total_seconds() // 60)
            if minutes <= 0:
                raise CrmError(
                    "invalid_schedule", "Appointment duration must be positive"
                )
            return ends, minutes

        minutes = duration_minutes
        if minutes is None and service is not None:
            minutes = service.duration_minutes
        if minutes is None:
            settings = self._settings.get_or_create(tenant_id)
            minutes = settings.slot_minutes
        if minutes <= 0:
            raise CrmError("invalid_duration", "duration_minutes must be positive")

        return starts + timedelta(minutes=minutes), minutes

    def _check_conflict(
        self,
        tenant_id: UUID,
        technician_id: UUID,
        starts: datetime,
        ends: datetime,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        q = select(Appointment).where(
            Appointment.tenant_id == tenant_id,
            Appointment.assigned_technician_id == technician_id,
            Appointment.archived_at.is_(None),
            Appointment.status.in_(ACTIVE_BOOKING_STATUSES),
            Appointment.starts_at < ends,
            Appointment.ends_at > starts,
        )
        if exclude_id is not None:
            q = q.where(Appointment.id != exclude_id)
        conflict = self._session.scalar(q.with_for_update())
        if conflict is not None:
            raise CrmError(
                "slot_conflict",
                "That technician already has an appointment in this time window",
            )

    # --- public API ---

    def get(self, tenant_id: UUID, appointment_id: UUID) -> dict[str, Any]:
        appt = self._load(tenant_id, appointment_id, include_history=True)
        return serialize_appointment(appt, include_history=True)

    def list(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.search.search(tenant_id, **kwargs)

    def create(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        starts_at: datetime,
        actor: str,
        service_type: str | None = None,
        service_id: UUID | None = None,
        duration_minutes: int | None = None,
        ends_at: datetime | None = None,
        location_id: UUID | None = None,
        technician_id: UUID | None = None,
        job_id: UUID | None = None,
        lead_id: UUID | None = None,
        call_id: UUID | None = None,
        priority: str | None = None,
        is_emergency: bool = False,
        notes: str | None = None,
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

        tech_id = None
        if technician_id is not None:
            self._require_technician(tenant_id, technician_id)
            tech_id = technician_id

        if job_id is not None:
            self._require_job(tenant_id, job_id, customer.id)

        try:
            prio = normalize_priority(priority)
        except ValueError as exc:
            raise CrmError("invalid_priority", str(exc)) from exc

        initial = DEFAULT_APPOINTMENT_STATUS
        if status:
            try:
                initial = normalize_status(status)
            except ValueError as exc:
                raise CrmError("invalid_status", str(exc)) from exc
            if initial not in _CREATABLE_STATUSES:
                raise CrmError(
                    "invalid_status",
                    "Appointments may only be created as TENTATIVE, SCHEDULED, or CONFIRMED",
                )

        notes_clean = None
        if notes is not None:
            notes_clean = notes.strip() or None
            if notes_clean and len(notes_clean) > NOTES_MAX_LEN:
                raise CrmError("invalid_notes", "notes is too long")
        if stype and len(stype) > DESCRIPTION_MAX_LEN:
            raise CrmError("invalid_service_type", "service_type is too long")

        starts = ensure_aware(starts_at)
        ends, duration = self._resolve_duration(
            tenant_id,
            starts=starts,
            ends_at=ends_at,
            duration_minutes=duration_minutes,
            service=svc,
        )
        tz_name = self._settings.effective_timezone(tenant_id)

        req_hash = appointment_create_fingerprint(
            customer_id=customer.id,
            location_id=location_id,
            service_id=service_id,
            service_type=stype,
            technician_id=tech_id,
            job_id=job_id,
            lead_id=lead_id,
            call_id=call_id,
            starts_at=starts,
            ends_at=ends,
            priority=prio,
            is_emergency=is_emergency,
            status=initial,
            notes=notes_clean,
        )

        if key:
            existing = self._session.scalar(
                select(Appointment).where(
                    Appointment.tenant_id == tenant_id,
                    Appointment.idempotency_key == key,
                )
            )
            if existing is not None:
                if (
                    existing.idempotency_request_hash
                    and existing.idempotency_request_hash != req_hash
                ):
                    raise CrmError(
                        "idempotency_conflict",
                        "Idempotency-Key reused with a different appointment payload",
                    )
                return self.get(tenant_id, existing.id)

        if tech_id is not None:
            self._check_conflict(tenant_id, tech_id, starts, ends)

        number = allocate_appointment_number(self._session, tenant_id)
        ref = appointment_ref()
        try:
            with self._session.begin_nested():
                appt = Appointment(
                    tenant_id=tenant_id,
                    appointment_number=number,
                    customer_id=customer.id,
                    lead_id=lead_id,
                    call_id=call_id,
                    job_id=job_id,
                    location_id=location_id,
                    service_id=service_id,
                    assigned_technician_id=tech_id,
                    starts_at=starts,
                    ends_at=ends,
                    duration_minutes=duration,
                    timezone=tz_name,
                    status=initial,
                    priority=prio,
                    is_emergency=is_emergency,
                    service_type=stype,
                    notes=notes_clean,
                    confirmation_code=ref,
                    idempotency_key=key,
                    idempotency_request_hash=req_hash if key else None,
                    created_by=actor,
                    updated_by=actor,
                )
                self._session.add(appt)
                self._session.flush()
        except IntegrityError as exc:
            if key:
                raced = self._session.scalar(
                    select(Appointment).where(
                        Appointment.tenant_id == tenant_id,
                        Appointment.idempotency_key == key,
                    )
                )
                if raced is not None:
                    if (
                        raced.idempotency_request_hash
                        and raced.idempotency_request_hash != req_hash
                    ):
                        raise CrmError(
                            "idempotency_conflict",
                            "Idempotency-Key reused with a different appointment payload",
                        ) from exc
                    return self.get(tenant_id, raced.id)
            # Dominant remaining IntegrityError source once idempotency and the
            # per-tenant number counter are ruled out: the PostgreSQL exclusion
            # constraint on (tenant, technician, active range) caught a race.
            raise CrmError(
                "slot_conflict",
                "That technician already has an appointment in this time window",
            ) from exc

        self._session.add(
            AppointmentStatusHistory(
                tenant_id=tenant_id,
                appointment_id=appt.id,
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
            action="appointment_created",
            resource_ids={
                "appointment_id": str(appt.id),
                "appointment_number": appt.appointment_number,
            },
            idempotency_key=key,
            payload_summary={"starts_at": starts.isoformat()},
        )
        return self.get(tenant_id, appt.id)

    def update(
        self,
        tenant_id: UUID,
        appointment_id: UUID,
        *,
        actor: str,
        notes: str | None = None,
        clear_notes: bool = False,
        priority: str | None = None,
        is_emergency: bool | None = None,
        location_id: UUID | None = None,
        clear_location: bool = False,
        service_type: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        if status is not None:
            raise CrmError(
                "use_transition",
                "Use POST /appointments/{id}/transition to change status",
            )
        appt = self._load(
            tenant_id, appointment_id, for_update=True, require_active=True
        )

        mutating = any(
            [
                clear_notes,
                notes is not None,
                priority is not None,
                is_emergency is not None,
                clear_location,
                location_id is not None,
                service_type is not None,
            ]
        )
        if mutating and appt.status not in EDITABLE_STATUSES:
            raise CrmError(
                "appointment_immutable",
                "Appointment fields are immutable once IN_PROGRESS or terminal; "
                "use transition/assign/reschedule APIs",
            )

        if clear_notes:
            appt.notes = None
        elif notes is not None:
            cleaned = notes.strip() or None
            if cleaned and len(cleaned) > NOTES_MAX_LEN:
                raise CrmError("invalid_notes", "notes is too long")
            appt.notes = cleaned

        if priority is not None:
            try:
                appt.priority = normalize_priority(priority)
            except ValueError as exc:
                raise CrmError("invalid_priority", str(exc)) from exc

        if is_emergency is not None:
            appt.is_emergency = is_emergency

        if clear_location:
            appt.location_id = None
        elif location_id is not None:
            self._require_location(tenant_id, appt.customer_id, location_id)
            appt.location_id = location_id

        if service_type is not None and service_type.strip():
            appt.service_type = service_type.strip()[:128]

        appt.updated_by = actor
        appt.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="appointment_updated",
            resource_ids={
                "appointment_id": str(appt.id),
                "appointment_number": appt.appointment_number,
            },
        )
        return self.get(tenant_id, appointment_id)

    def assign(
        self,
        tenant_id: UUID,
        appointment_id: UUID,
        *,
        technician_id: UUID | None,
        actor: str,
    ) -> dict[str, Any]:
        appt = self._load(
            tenant_id, appointment_id, for_update=True, require_active=True
        )
        if appt.status not in ASSIGNABLE_STATUSES:
            raise CrmError(
                "invalid_transition",
                f"Cannot assign/unassign technician while appointment is {appt.status}",
            )
        prev = appt.assigned_technician_id
        if technician_id is None:
            appt.assigned_technician_id = None
            action = "appointment_unassigned"
        else:
            self._require_technician(tenant_id, technician_id)
            if appt.status in ACTIVE_BOOKING_STATUSES:
                self._check_conflict(
                    tenant_id,
                    technician_id,
                    appt.starts_at,
                    appt.ends_at,
                    exclude_id=appt.id,
                )
            appt.assigned_technician_id = technician_id
            action = "appointment_assigned"
        appt.updated_by = actor
        appt.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action=action,
            resource_ids={
                "appointment_id": str(appt.id),
                "technician_id": str(technician_id) if technician_id else None,
                "previous_technician_id": str(prev) if prev else None,
            },
        )
        return self.get(tenant_id, appointment_id)

    def reschedule(
        self,
        tenant_id: UUID,
        appointment_id: UUID,
        *,
        starts_at: datetime,
        actor: str,
        ends_at: datetime | None = None,
        duration_minutes: int | None = None,
    ) -> dict[str, Any]:
        appt = self._load(
            tenant_id, appointment_id, for_update=True, require_active=True
        )
        if appt.status in TERMINAL_STATUSES:
            raise CrmError(
                "invalid_transition",
                f"Cannot reschedule an appointment that is {appt.status}",
            )
        starts = ensure_aware(starts_at)
        svc = None
        if appt.service_id is not None:
            svc = self._session.scalar(
                select(Service).where(Service.id == appt.service_id)
            )
        ends, duration = self._resolve_duration(
            tenant_id,
            starts=starts,
            ends_at=ends_at,
            duration_minutes=duration_minutes
            if duration_minutes is not None
            else (None if ends_at is not None else appt.duration_minutes),
            service=svc,
        )

        if (
            appt.assigned_technician_id is not None
            and appt.status in ACTIVE_BOOKING_STATUSES
        ):
            self._check_conflict(
                tenant_id,
                appt.assigned_technician_id,
                starts,
                ends,
                exclude_id=appt.id,
            )

        old_starts = appt.starts_at
        old_ends = appt.ends_at
        appt.starts_at = starts
        appt.ends_at = ends
        appt.duration_minutes = duration
        appt.updated_by = actor
        appt.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="appointment_rescheduled",
            resource_ids={
                "appointment_id": str(appt.id),
                "appointment_number": appt.appointment_number,
            },
            payload_summary={
                "old_starts_at": old_starts.isoformat() if old_starts else None,
                "old_ends_at": old_ends.isoformat() if old_ends else None,
                "starts_at": starts.isoformat(),
                "ends_at": ends.isoformat(),
            },
        )
        return self.get(tenant_id, appointment_id)

    def cancel(
        self,
        tenant_id: UUID,
        appointment_id: UUID,
        *,
        actor: str,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return self.transitions.transition(
            tenant_id,
            appointment_id,
            to_status=AppointmentStatus.CANCELLED.value,
            actor=actor,
            reason=reason,
        )

    def transition(
        self, tenant_id: UUID, appointment_id: UUID, **kwargs: Any
    ) -> dict[str, Any]:
        return self.transitions.transition(tenant_id, appointment_id, **kwargs)

    def history(self, tenant_id: UUID, appointment_id: UUID) -> list[dict[str, Any]]:
        return self.transitions.history(tenant_id, appointment_id)

    def archive(
        self, tenant_id: UUID, appointment_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        appt = self._load(tenant_id, appointment_id, for_update=True)
        if appt.archived_at is not None:
            return self.get(tenant_id, appointment_id)
        if appt.status not in _ARCHIVABLE_STATUSES:
            raise CrmError(
                "archive_not_allowed",
                "Only TENTATIVE, COMPLETED, CANCELLED, or NO_SHOW appointments "
                "can be archived",
            )
        appt.archived_at = datetime.now(UTC)
        appt.updated_by = actor
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="appointment_archived",
            resource_ids={"appointment_id": str(appt.id)},
        )
        return self.get(tenant_id, appointment_id)

    def restore(
        self, tenant_id: UUID, appointment_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        appt = self._load(tenant_id, appointment_id, for_update=True)
        if appt.archived_at is None:
            return self.get(tenant_id, appointment_id)
        appt.archived_at = None
        appt.updated_by = actor
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="appointment_restored",
            resource_ids={"appointment_id": str(appt.id)},
        )
        return self.get(tenant_id, appointment_id)
