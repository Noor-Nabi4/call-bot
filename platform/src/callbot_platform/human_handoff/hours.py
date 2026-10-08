"""Reuse BusinessHoursService / schedule settings for handoff after-hours checks."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.scheduling import BusinessHoliday
from callbot_platform.scheduling.availability import parse_hhmm
from callbot_platform.scheduling.repos.settings_repo import ScheduleSettingsRepository

_DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


def _weekday_key(local_dt: datetime) -> str:
    # Monday=0
    return _DAY_KEYS[local_dt.weekday()]


class HandoffHoursService:
    """Thin adapter over existing schedule settings — no duplicate hours store."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._settings = ScheduleSettingsRepository(session)

    def status_at(
        self, tenant_id: UUID, *, when: datetime | None = None
    ) -> dict[str, Any]:
        from callbot_platform.db.models import Tenant

        tenant = self._session.get(Tenant, tenant_id)
        settings = self._settings.get_or_create(tenant_id)
        tz_name = (tenant.timezone if tenant else None) or "UTC"
        try:
            tz = ZoneInfo(tz_name)
        except Exception:
            tz = ZoneInfo("UTC")
            tz_name = "UTC"

        moment = when or datetime.now(UTC)
        if moment.tzinfo is None:
            moment = moment.replace(tzinfo=UTC)
        local = moment.astimezone(tz)
        local_date = local.date()

        holiday = self._session.scalar(
            select(BusinessHoliday).where(
                BusinessHoliday.tenant_id == tenant_id,
                BusinessHoliday.holiday_date == local_date,
            )
        )
        if holiday is not None:
            return {
                "in_business_hours": False,
                "after_hours": True,
                "holiday": True,
                "holiday_name": holiday.name,
                "timezone": tz_name,
                "local_time": local.isoformat(),
            }

        weekly = settings.weekly_hours or {}
        day_key = _weekday_key(local)
        windows = weekly.get(day_key) or []
        in_hours = False
        for window in windows:
            if not isinstance(window, (list, tuple)) or len(window) != 2:
                continue
            try:
                open_t = parse_hhmm(str(window[0]))
                close_t = parse_hhmm(str(window[1]))
            except (ValueError, IndexError):
                continue
            local_t = local.time().replace(tzinfo=None)
            if open_t <= local_t < close_t:
                in_hours = True
                break

        return {
            "in_business_hours": in_hours,
            "after_hours": not in_hours,
            "holiday": False,
            "holiday_name": None,
            "timezone": tz_name,
            "local_time": local.isoformat(),
        }
