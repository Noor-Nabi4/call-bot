"""Availability engine (Phase 11) — advisory free/busy computation.

Combines business hours (or emergency hours), technician schedules, breaks,
time off, existing active appointments, required skills, and service-area
matching to produce candidate appointment slots.

This is **advisory only**: it helps the UI/AI suggest times, but it is not
the source of truth for conflict prevention. ``AppointmentService.create``
and ``.reschedule`` re-validate against the database inside a transaction
and rely on the PostgreSQL exclusion constraint
(``excl_appointments_technician_active_range``) as the authoritative,
race-safe guard against double-booking.

Half-open intervals ``[start, end)`` throughout.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.appointments.constants import (
    ACTIVE_BOOKING_STATUSES,
    DAY_KEYS,
)
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.crm import CustomerLocation
from callbot_platform.db.models.jobs import Technician
from callbot_platform.db.models.scheduling import (
    Appointment,
    BusinessHoliday,
    ServiceArea,
    ServiceRequiredSkill,
    TechnicianBreak,
    TechnicianSchedulePeriod,
    TechnicianServiceArea,
    TechnicianSkill,
    TechnicianTimeOff,
    default_weekly_hours,
)
from callbot_platform.db.models.services.service import Service
from callbot_platform.scheduling.availability import resolve_tz
from callbot_platform.scheduling.repos.settings_repo import ScheduleSettingsRepository

_LOCATION_FIELD_BY_MATCH_TYPE = {
    "POSTAL_CODE": "postal_code",
    "CITY": "city",
    "REGION": "state",
}


@dataclass(frozen=True, slots=True)
class AvailabilitySlot:
    starts_at: datetime  # UTC
    ends_at: datetime  # UTC
    local_start: str
    local_end: str
    technician_id: str
    technician_name: str


def _time_windows_for_day(
    weekly_hours: dict[str, Any], day_key: str
) -> list[tuple[time, time]]:
    out: list[tuple[time, time]] = []
    for window in weekly_hours.get(day_key) or []:
        if not isinstance(window, (list, tuple)) or len(window) != 2:
            continue
        h1, m1 = str(window[0]).split(":")
        h2, m2 = str(window[1]).split(":")
        out.append((time(int(h1), int(m1)), time(int(h2), int(m2))))
    return out


def _intersect_time_windows(
    a: list[tuple[time, time]], b: list[tuple[time, time]]
) -> list[tuple[time, time]]:
    out: list[tuple[time, time]] = []
    for a_start, a_end in a:
        for b_start, b_end in b:
            start = max(a_start, b_start)
            end = min(a_end, b_end)
            if start < end:
                out.append((start, end))
    return out


def _to_datetime_windows(
    day: date, windows: list[tuple[time, time]], tz: ZoneInfo
) -> list[tuple[datetime, datetime]]:
    out: list[tuple[datetime, datetime]] = []
    for start_t, end_t in windows:
        start_dt = datetime.combine(day, start_t, tzinfo=tz).astimezone(UTC)
        end_dt = datetime.combine(day, end_t, tzinfo=tz).astimezone(UTC)
        if start_dt < end_dt:
            out.append((start_dt, end_dt))
    return out


def _subtract_ranges(
    windows: list[tuple[datetime, datetime]],
    busy: list[tuple[datetime, datetime]],
) -> list[tuple[datetime, datetime]]:
    """Subtract half-open busy ranges from half-open free windows."""
    if not busy:
        return list(windows)
    result: list[tuple[datetime, datetime]] = []
    for w_start, w_end in windows:
        segments = [(w_start, w_end)]
        for b_start, b_end in busy:
            next_segments: list[tuple[datetime, datetime]] = []
            for s_start, s_end in segments:
                if b_end <= s_start or b_start >= s_end:
                    next_segments.append((s_start, s_end))
                    continue
                if b_start > s_start:
                    next_segments.append((s_start, b_start))
                if b_end < s_end:
                    next_segments.append((b_end, s_end))
            segments = next_segments
        result.extend(segments)
    return [seg for seg in result if seg[0] < seg[1]]


class AvailabilityEngine:
    """Computes advisory free appointment slots per technician."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = ScheduleSettingsRepository(session)

    def compute(
        self,
        tenant_id: UUID,
        *,
        from_date: date,
        to_date: date,
        service_id: UUID | None = None,
        duration_minutes: int | None = None,
        technician_id: UUID | None = None,
        is_emergency: bool = False,
        location_id: UUID | None = None,
        limit: int = 50,
        now_utc: datetime | None = None,
    ) -> dict[str, Any]:
        if to_date < from_date:
            raise CrmError("invalid_range", "to_date must be on or after from_date")

        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise CrmError("tenant_not_found", "Tenant not found")

        settings = self._settings.get_or_create(tenant_id)
        tz_name = self._settings.effective_timezone(tenant_id)
        tz = resolve_tz(tz_name)
        now = now_utc or datetime.now(UTC)
        if now.tzinfo is None:
            now = now.replace(tzinfo=UTC)

        weekly_hours = (
            settings.emergency_weekly_hours
            if is_emergency
            else (settings.weekly_hours or default_weekly_hours())
        ) or {}

        service: Service | None = None
        if service_id is not None:
            service = self._session.scalar(
                select(Service).where(
                    Service.id == service_id, Service.tenant_id == tenant_id
                )
            )
            if service is None or service.archived_at is not None:
                raise CrmError("service_not_found", "Service not found for tenant")

        duration = (
            duration_minutes
            or (
                service.duration_minutes
                if service and service.duration_minutes
                else None
            )
            or settings.slot_minutes
        )
        if duration <= 0:
            raise CrmError("invalid_duration", "duration_minutes must be positive")

        holiday_dates = set(
            self._session.scalars(
                select(BusinessHoliday.holiday_date).where(
                    BusinessHoliday.tenant_id == tenant_id,
                    BusinessHoliday.holiday_date >= from_date,
                    BusinessHoliday.holiday_date <= to_date,
                    BusinessHoliday.is_full_day.is_(True),
                )
            ).all()
        )

        required_skill_ids: set[UUID] = set()
        if service_id is not None:
            required_skill_ids = set(
                self._session.scalars(
                    select(ServiceRequiredSkill.skill_id).where(
                        ServiceRequiredSkill.tenant_id == tenant_id,
                        ServiceRequiredSkill.service_id == service_id,
                    )
                ).all()
            )

        location: CustomerLocation | None = None
        matching_area_ids: set[UUID] = set()
        tenant_has_service_areas = False
        if location_id is not None:
            location = self._session.scalar(
                select(CustomerLocation).where(
                    CustomerLocation.id == location_id,
                    CustomerLocation.tenant_id == tenant_id,
                )
            )
            if location is None or location.archived_at is not None:
                raise CrmError("location_not_found", "Location not found for tenant")
            areas = list(
                self._session.scalars(
                    select(ServiceArea).where(
                        ServiceArea.tenant_id == tenant_id,
                        ServiceArea.archived_at.is_(None),
                    )
                ).all()
            )
            tenant_has_service_areas = len(areas) > 0
            for area in areas:
                field = _LOCATION_FIELD_BY_MATCH_TYPE.get(area.match_type)
                if field is None:
                    continue
                loc_value = (getattr(location, field, None) or "").strip().lower()
                if loc_value and loc_value == area.match_value.strip().lower():
                    matching_area_ids.add(area.id)

        # --- Candidate technicians ---
        tech_q = select(Technician).where(
            Technician.tenant_id == tenant_id, Technician.is_active.is_(True)
        )
        if technician_id is not None:
            tech_q = tech_q.where(Technician.id == technician_id)
        technicians = list(self._session.scalars(tech_q).all())
        if technician_id is not None and not technicians:
            raise CrmError("technician_not_found", "Technician not found for tenant")

        if required_skill_ids:
            tech_skill_map: dict[UUID, set[UUID]] = {}
            rows = self._session.execute(
                select(TechnicianSkill.technician_id, TechnicianSkill.skill_id).where(
                    TechnicianSkill.tenant_id == tenant_id,
                    TechnicianSkill.technician_id.in_([t.id for t in technicians]),
                )
            ).all()
            for tech_id, skill_id in rows:
                tech_skill_map.setdefault(tech_id, set()).add(skill_id)
            technicians = [
                t
                for t in technicians
                if required_skill_ids.issubset(tech_skill_map.get(t.id, set()))
            ]

        if location is not None and tenant_has_service_areas:
            tech_area_map: dict[UUID, set[UUID]] = {}
            rows = self._session.execute(
                select(
                    TechnicianServiceArea.technician_id,
                    TechnicianServiceArea.service_area_id,
                ).where(
                    TechnicianServiceArea.tenant_id == tenant_id,
                    TechnicianServiceArea.technician_id.in_(
                        [t.id for t in technicians]
                    ),
                )
            ).all()
            for tech_id, area_id in rows:
                tech_area_map.setdefault(tech_id, set()).add(area_id)
            technicians = [
                t
                for t in technicians
                if tech_area_map.get(t.id, set()) & matching_area_ids
            ]

        if not technicians:
            return {
                "timezone": tz_name,
                "slot_minutes": settings.slot_minutes,
                "duration_minutes": duration,
                "is_emergency": is_emergency,
                "slots": [],
            }

        tech_ids = [t.id for t in technicians]

        # --- Bulk-load tech schedule facts ---
        periods_by_tech: dict[UUID, list[TechnicianSchedulePeriod]] = {}
        for row in self._session.scalars(
            select(TechnicianSchedulePeriod).where(
                TechnicianSchedulePeriod.tenant_id == tenant_id,
                TechnicianSchedulePeriod.technician_id.in_(tech_ids),
            )
        ).all():
            periods_by_tech.setdefault(row.technician_id, []).append(row)

        breaks_by_tech: dict[UUID, list[TechnicianBreak]] = {}
        for row in self._session.scalars(
            select(TechnicianBreak).where(
                TechnicianBreak.tenant_id == tenant_id,
                TechnicianBreak.technician_id.in_(tech_ids),
            )
        ).all():
            breaks_by_tech.setdefault(row.technician_id, []).append(row)

        window_start_utc = datetime.combine(from_date, time.min, tzinfo=tz).astimezone(
            UTC
        )
        window_end_utc = datetime.combine(
            to_date + timedelta(days=1), time.min, tzinfo=tz
        ).astimezone(UTC)

        time_off_by_tech: dict[UUID, list[tuple[datetime, datetime]]] = {}
        for row in self._session.scalars(
            select(TechnicianTimeOff).where(
                TechnicianTimeOff.tenant_id == tenant_id,
                TechnicianTimeOff.technician_id.in_(tech_ids),
                TechnicianTimeOff.starts_at < window_end_utc,
                TechnicianTimeOff.ends_at > window_start_utc,
            )
        ).all():
            starts = (
                row.starts_at
                if row.starts_at.tzinfo
                else row.starts_at.replace(tzinfo=UTC)
            )
            ends = (
                row.ends_at if row.ends_at.tzinfo else row.ends_at.replace(tzinfo=UTC)
            )
            time_off_by_tech.setdefault(row.technician_id, []).append((starts, ends))

        booked_by_tech: dict[UUID, list[tuple[datetime, datetime]]] = {}
        for row in self._session.scalars(
            select(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.assigned_technician_id.in_(tech_ids),
                Appointment.archived_at.is_(None),
                Appointment.status.in_(ACTIVE_BOOKING_STATUSES),
                Appointment.starts_at < window_end_utc,
                Appointment.ends_at > window_start_utc,
            )
        ).all():
            starts = (
                row.starts_at
                if row.starts_at.tzinfo
                else row.starts_at.replace(tzinfo=UTC)
            )
            ends = (
                row.ends_at if row.ends_at.tzinfo else row.ends_at.replace(tzinfo=UTC)
            )
            booked_by_tech.setdefault(row.assigned_technician_id, []).append(
                (starts, ends)
            )

        step = timedelta(minutes=max(1, settings.slot_minutes))
        duration_delta = timedelta(minutes=duration)
        slots: list[AvailabilitySlot] = []

        day = from_date
        while day <= to_date:
            if day in holiday_dates:
                day += timedelta(days=1)
                continue
            day_key = DAY_KEYS[day.weekday()]
            business_windows = _time_windows_for_day(weekly_hours, day_key)
            if not business_windows:
                day += timedelta(days=1)
                continue

            for tech in technicians:
                tech_periods = periods_by_tech.get(tech.id)
                if tech_periods:
                    today_periods = [
                        (p.open_time, p.close_time)
                        for p in tech_periods
                        if p.day_of_week == day.weekday()
                    ]
                    if not today_periods:
                        continue  # Technician explicitly has no hours this day.
                    effective_windows = _intersect_time_windows(
                        business_windows, today_periods
                    )
                else:
                    # No periods configured for this technician at all — fall
                    # back to business hours only.
                    effective_windows = list(business_windows)

                if not effective_windows:
                    continue

                dt_windows = _to_datetime_windows(day, effective_windows, tz)

                today_breaks = [
                    (b.start_time, b.end_time)
                    for b in breaks_by_tech.get(tech.id, [])
                    if b.day_of_week == day.weekday()
                ]
                if today_breaks:
                    break_dt = _to_datetime_windows(day, today_breaks, tz)
                    dt_windows = _subtract_ranges(dt_windows, break_dt)

                busy = time_off_by_tech.get(tech.id, []) + booked_by_tech.get(
                    tech.id, []
                )
                dt_windows = _subtract_ranges(dt_windows, busy)

                for w_start, w_end in dt_windows:
                    cursor = w_start
                    while cursor + duration_delta <= w_end:
                        if cursor >= now:
                            local_start = cursor.astimezone(tz)
                            local_end = (cursor + duration_delta).astimezone(tz)
                            slots.append(
                                AvailabilitySlot(
                                    starts_at=cursor,
                                    ends_at=cursor + duration_delta,
                                    local_start=local_start.isoformat(),
                                    local_end=local_end.isoformat(),
                                    technician_id=str(tech.id),
                                    technician_name=tech.display_name,
                                )
                            )
                        cursor += step
            day += timedelta(days=1)

        slots.sort(key=lambda s: (s.starts_at, s.technician_name))
        bounded = slots[: max(1, min(limit, 500))]
        return {
            "timezone": tz_name,
            "slot_minutes": settings.slot_minutes,
            "duration_minutes": duration,
            "is_emergency": is_emergency,
            "slots": [
                {
                    "starts_at": s.starts_at.isoformat(),
                    "ends_at": s.ends_at.isoformat(),
                    "local_start": s.local_start,
                    "local_end": s.local_end,
                    "technician_id": s.technician_id,
                    "technician_name": s.technician_name,
                }
                for s in bounded
            ],
        }
