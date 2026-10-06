"""Business hours validation and holiday CRUD (Phase 11)."""

from __future__ import annotations

from datetime import UTC, date, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.crm.appointments.constants import DAY_KEYS
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.scheduling import BusinessHoliday
from callbot_platform.scheduling.availability import parse_hhmm
from callbot_platform.scheduling.repos.settings_repo import ScheduleSettingsRepository
from callbot_platform.telephony.audit import write_audit

HOLIDAY_NAME_MAX_LEN = 255


def validate_weekly_hours(weekly_hours: Any) -> dict[str, list[list[str]]]:
    """Validate a weekly-hours payload: valid day keys, open < close, no overlap.

    Shape: ``{"mon": [["09:00", "17:00"]], "sat": [], ...}``. Half-open
    intervals ``[open, close)`` — a window ending at the same time another
    begins is allowed (back-to-back), not an overlap.
    """
    if not isinstance(weekly_hours, dict):
        raise CrmError("invalid_weekly_hours", "weekly_hours must be an object")
    unknown = set(weekly_hours.keys()) - set(DAY_KEYS)
    if unknown:
        raise CrmError("invalid_weekly_hours", f"Unknown day keys: {sorted(unknown)}")

    cleaned: dict[str, list[list[str]]] = {}
    for day in DAY_KEYS:
        windows = weekly_hours.get(day) or []
        if not isinstance(windows, list):
            raise CrmError(
                "invalid_weekly_hours", f"weekly_hours[{day}] must be a list"
            )
        parsed: list[tuple[Any, Any]] = []
        for window in windows:
            if not isinstance(window, (list, tuple)) or len(window) != 2:
                raise CrmError(
                    "invalid_weekly_hours",
                    f"weekly_hours[{day}] windows must be [open, close] pairs",
                )
            try:
                open_t = parse_hhmm(str(window[0]))
                close_t = parse_hhmm(str(window[1]))
            except (ValueError, IndexError) as exc:
                raise CrmError(
                    "invalid_weekly_hours",
                    f"weekly_hours[{day}] has an invalid HH:MM value",
                ) from exc
            if open_t >= close_t:
                raise CrmError(
                    "invalid_weekly_hours",
                    f"weekly_hours[{day}] window open time must be before close "
                    "(overnight periods like 22:00–02:00 are not supported)",
                )
            parsed.append((open_t, close_t))

        parsed.sort(key=lambda w: w[0])
        for i in range(1, len(parsed)):
            if parsed[i][0] < parsed[i - 1][1]:
                raise CrmError(
                    "invalid_weekly_hours",
                    f"weekly_hours[{day}] has overlapping windows",
                )
        cleaned[day] = [
            [open_t.strftime("%H:%M"), close_t.strftime("%H:%M")]
            for open_t, close_t in parsed
        ]
    return cleaned


class BusinessHoursService:
    """Business hours (weekly + emergency) and holiday management."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = ScheduleSettingsRepository(session)

    def get(self, tenant_id: UUID) -> dict[str, Any]:
        from callbot_platform.db.models import Tenant

        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise CrmError("tenant_not_found", "Tenant not found")
        settings = self._settings.get_or_create(tenant_id)
        payload = self._settings.serialize(settings, tenant)
        payload["emergency_weekly_hours"] = settings.emergency_weekly_hours
        return payload

    def update(
        self,
        tenant_id: UUID,
        *,
        actor: str,
        timezone: str | None = None,
        slot_minutes: int | None = None,
        booking_horizon_days: int | None = None,
        weekly_hours: dict[str, Any] | None = None,
        emergency_weekly_hours: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        settings = self._settings.get_or_create(tenant_id)
        if timezone is not None:
            from callbot_platform.scheduling.availability import resolve_tz

            try:
                resolve_tz(timezone)
            except ValueError as exc:
                raise CrmError("invalid_timezone", str(exc)) from exc
            settings.timezone = timezone.strip() or None
        if slot_minutes is not None:
            if slot_minutes <= 0 or slot_minutes > 24 * 60:
                raise CrmError(
                    "invalid_slot_minutes", "slot_minutes must be between 1 and 1440"
                )
            settings.slot_minutes = slot_minutes
        if booking_horizon_days is not None:
            if booking_horizon_days <= 0 or booking_horizon_days > 365:
                raise CrmError(
                    "invalid_booking_horizon",
                    "booking_horizon_days must be between 1 and 365",
                )
            settings.booking_horizon_days = booking_horizon_days
        if weekly_hours is not None:
            settings.weekly_hours = validate_weekly_hours(weekly_hours)
        if emergency_weekly_hours is not None:
            settings.emergency_weekly_hours = validate_weekly_hours(
                emergency_weekly_hours
            )
        settings.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="business_hours_updated",
            resource_ids={"tenant_id": str(tenant_id)},
        )
        return self.get(tenant_id)

    def list_holidays(
        self, tenant_id: UUID, *, from_date: date | None = None
    ) -> list[dict[str, Any]]:
        q = select(BusinessHoliday).where(BusinessHoliday.tenant_id == tenant_id)
        if from_date is not None:
            q = q.where(BusinessHoliday.holiday_date >= from_date)
        q = q.order_by(BusinessHoliday.holiday_date.asc())
        return [self._serialize_holiday(r) for r in self._session.scalars(q).all()]

    def create_holiday(
        self,
        tenant_id: UUID,
        *,
        holiday_date: date,
        name: str,
        is_full_day: bool = True,
        actor: str,
    ) -> dict[str, Any]:
        clean_name = (name or "").strip()
        if not clean_name:
            raise CrmError("invalid_holiday", "name is required")
        if len(clean_name) > HOLIDAY_NAME_MAX_LEN:
            raise CrmError("invalid_holiday", "name is too long")
        row = BusinessHoliday(
            tenant_id=tenant_id,
            holiday_date=holiday_date,
            name=clean_name,
            is_full_day=is_full_day,
        )
        try:
            # `row` must be added *inside* the nested transaction: entering
            # begin_nested() flushes any already-pending objects first (to
            # snapshot state before the SAVEPOINT), so adding beforehand
            # would raise the IntegrityError outside the savepoint and
            # poison the whole session instead of being caught here.
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "holiday_conflict", "A holiday already exists for that date"
            ) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="holiday_created",
            resource_ids={"holiday_id": str(row.id)},
        )
        return self._serialize_holiday(row)

    def delete_holiday(self, tenant_id: UUID, holiday_id: UUID, *, actor: str) -> None:
        row = self._session.scalar(
            select(BusinessHoliday).where(
                BusinessHoliday.id == holiday_id,
                BusinessHoliday.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Holiday not found for tenant")
        self._session.delete(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="holiday_deleted",
            resource_ids={"holiday_id": str(holiday_id)},
        )

    @staticmethod
    def _serialize_holiday(row: BusinessHoliday) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "holiday_date": row.holiday_date.isoformat(),
            "name": row.name,
            "is_full_day": row.is_full_day,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
