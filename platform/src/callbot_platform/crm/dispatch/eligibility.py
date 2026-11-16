"""Dispatch assignment eligibility — reuses Phase 11 skills/areas/schedule facts."""

from __future__ import annotations

from datetime import UTC, time, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.appointments.constants import ACTIVE_BOOKING_STATUSES
from callbot_platform.crm.dispatch.constants import UNASSIGNABLE_TECH_STATUSES
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.crm import CustomerLocation
from callbot_platform.db.models.dispatch import TechnicianOperationalStatus
from callbot_platform.db.models.jobs import Job, Technician
from callbot_platform.db.models.scheduling import (
    Appointment,
    ServiceArea,
    ServiceRequiredSkill,
    TechnicianBreak,
    TechnicianSchedulePeriod,
    TechnicianServiceArea,
    TechnicianSkill,
    TechnicianTimeOff,
)
from callbot_platform.db.models.services.service import Service

_LOCATION_FIELD_BY_MATCH_TYPE = {
    "POSTAL_CODE": "postal_code",
    "CITY": "city",
    "REGION": "state",
}


class AssignmentEligibility:
    """Server-side eligibility checks before authoritative job assignment."""

    def __init__(self, session: Session) -> None:
        self._session = session

    def assert_assignable(
        self,
        tenant_id: UUID,
        job: Job,
        technician_id: UUID,
        *,
        skip_operational_status: bool = False,
    ) -> Technician:
        tech = self._session.scalar(
            select(Technician).where(
                Technician.id == technician_id,
                Technician.tenant_id == tenant_id,
            )
        )
        if tech is None or not tech.is_active:
            raise CrmError("technician_not_found", "Technician not found for tenant")

        if not skip_operational_status:
            ops = self._session.scalar(
                select(TechnicianOperationalStatus).where(
                    TechnicianOperationalStatus.tenant_id == tenant_id,
                    TechnicianOperationalStatus.technician_id == technician_id,
                )
            )
            # Missing row = legacy / not yet backfilled → treat as AVAILABLE.
            if ops is not None and ops.status in UNASSIGNABLE_TECH_STATUSES:
                raise CrmError(
                    "technician_unavailable",
                    f"Technician is {ops.status} and cannot receive new assignments",
                )

        self._assert_skills(tenant_id, job, technician_id)
        self._assert_service_area(tenant_id, job, technician_id)
        self._assert_schedule_window(tenant_id, job, technician_id)
        self._assert_appointment_conflict(tenant_id, job, technician_id)
        return tech

    def _assert_skills(self, tenant_id: UUID, job: Job, technician_id: UUID) -> None:
        if job.service_id is None:
            return
        required = list(
            self._session.scalars(
                select(ServiceRequiredSkill.skill_id).where(
                    ServiceRequiredSkill.tenant_id == tenant_id,
                    ServiceRequiredSkill.service_id == job.service_id,
                )
            ).all()
        )
        if not required:
            return
        owned = set(
            self._session.scalars(
                select(TechnicianSkill.skill_id).where(
                    TechnicianSkill.tenant_id == tenant_id,
                    TechnicianSkill.technician_id == technician_id,
                )
            ).all()
        )
        missing = [str(s) for s in required if s not in owned]
        if missing:
            raise CrmError(
                "skill_mismatch",
                "Technician is missing one or more required skills for this job",
            )

        # Service category eligibility: if the service has a category, ensure
        # the technician has at least one skill tied to required skills for
        # that service (already enforced). No separate tech↔category table.
        svc = self._session.scalar(
            select(Service).where(
                Service.id == job.service_id, Service.tenant_id == tenant_id
            )
        )
        if svc is None or getattr(svc, "archived_at", None) is not None:
            raise CrmError("service_not_found", "Service not found for tenant")

    def _assert_service_area(
        self, tenant_id: UUID, job: Job, technician_id: UUID
    ) -> None:
        if job.location_id is None:
            return
        links = list(
            self._session.scalars(
                select(TechnicianServiceArea).where(
                    TechnicianServiceArea.tenant_id == tenant_id,
                    TechnicianServiceArea.technician_id == technician_id,
                )
            ).all()
        )
        if not links:
            return  # no areas configured → no geographic restriction
        location = self._session.scalar(
            select(CustomerLocation).where(
                CustomerLocation.id == job.location_id,
                CustomerLocation.tenant_id == tenant_id,
            )
        )
        if location is None:
            raise CrmError("location_not_found", "Location not found for tenant")
        area_ids = [lnk.service_area_id for lnk in links]
        areas = list(
            self._session.scalars(
                select(ServiceArea).where(
                    ServiceArea.tenant_id == tenant_id,
                    ServiceArea.id.in_(area_ids),
                    ServiceArea.archived_at.is_(None),
                )
            ).all()
        )
        for area in areas:
            field = _LOCATION_FIELD_BY_MATCH_TYPE.get(area.match_type)
            if not field:
                continue
            value = (getattr(location, field, None) or "").strip().lower()
            target = (area.match_value or "").strip().lower()
            if value and target and value == target:
                return
        raise CrmError(
            "service_area_mismatch",
            "Technician service areas do not cover the job location",
        )

    def _assert_schedule_window(
        self, tenant_id: UUID, job: Job, technician_id: UUID
    ) -> None:
        starts = job.scheduled_starts_at
        ends = job.scheduled_ends_at
        if starts is None:
            return
        if starts.tzinfo is None:
            starts = starts.replace(tzinfo=UTC)
        if ends is None:
            ends = starts + timedelta(hours=1)
        elif ends.tzinfo is None:
            ends = ends.replace(tzinfo=UTC)

        time_off = list(
            self._session.scalars(
                select(TechnicianTimeOff).where(
                    TechnicianTimeOff.tenant_id == tenant_id,
                    TechnicianTimeOff.technician_id == technician_id,
                    TechnicianTimeOff.starts_at < ends,
                    TechnicianTimeOff.ends_at > starts,
                )
            ).all()
        )
        if time_off:
            raise CrmError(
                "time_off_conflict",
                "Technician has time off overlapping the job window",
            )

        # Breaks / schedule periods use local wall-clock day-of-week relative to UTC
        # when tenant TZ is unavailable here — board uses tenant TZ; assignment
        # still rejects when a break fully covers the UTC wall-clock day portion.
        dow = starts.astimezone(UTC).weekday()  # Mon=0
        periods = list(
            self._session.scalars(
                select(TechnicianSchedulePeriod).where(
                    TechnicianSchedulePeriod.tenant_id == tenant_id,
                    TechnicianSchedulePeriod.technician_id == technician_id,
                    TechnicianSchedulePeriod.day_of_week == dow,
                )
            ).all()
        )
        if periods:
            start_t = starts.astimezone(UTC).time().replace(tzinfo=None)
            end_t = ends.astimezone(UTC).time().replace(tzinfo=None)
            if end_t <= start_t:
                end_t = time(23, 59)
            covered = False
            for p in periods:
                if p.open_time <= start_t and end_t <= p.close_time:
                    covered = True
                    break
                if p.open_time < end_t and start_t < p.close_time:
                    covered = True
                    break
            if not covered:
                raise CrmError(
                    "schedule_conflict",
                    "Job window is outside the technician schedule",
                )

        breaks = list(
            self._session.scalars(
                select(TechnicianBreak).where(
                    TechnicianBreak.tenant_id == tenant_id,
                    TechnicianBreak.technician_id == technician_id,
                    TechnicianBreak.day_of_week == dow,
                )
            ).all()
        )
        start_t = starts.astimezone(UTC).time().replace(tzinfo=None)
        end_t = ends.astimezone(UTC).time().replace(tzinfo=None)
        for br in breaks:
            if br.start_time < end_t and start_t < br.end_time:
                raise CrmError(
                    "schedule_conflict",
                    "Job window overlaps a technician break",
                )

    def _assert_appointment_conflict(
        self, tenant_id: UUID, job: Job, technician_id: UUID
    ) -> None:
        starts = job.scheduled_starts_at
        if starts is None:
            return
        if starts.tzinfo is None:
            starts = starts.replace(tzinfo=UTC)
        ends = job.scheduled_ends_at or (starts + timedelta(hours=1))
        if ends.tzinfo is None:
            ends = ends.replace(tzinfo=UTC)
        conflict = self._session.scalar(
            select(Appointment.id)
            .where(
                Appointment.tenant_id == tenant_id,
                Appointment.assigned_technician_id == technician_id,
                Appointment.archived_at.is_(None),
                Appointment.status.in_(tuple(ACTIVE_BOOKING_STATUSES)),
                Appointment.starts_at < ends,
                Appointment.ends_at > starts,
            )
            .limit(1)
        )
        if conflict is not None:
            # Allow if the conflicting appointment is the job's own linked appt.
            if job.appointment_id is not None and conflict == job.appointment_id:
                return
            raise CrmError(
                "schedule_conflict",
                "Technician has a conflicting appointment in this window",
            )
