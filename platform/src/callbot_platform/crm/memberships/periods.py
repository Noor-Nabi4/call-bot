"""Billing period arithmetic (calendar months / years)."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime

from callbot_platform.crm.memberships.constants import BillingInterval


def ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def add_calendar_months(dt: datetime, months: int) -> datetime:
    """Add calendar months preserving wall time; clamp day to month length."""
    dt = ensure_utc(dt)
    year = dt.year + (dt.month - 1 + months) // 12
    month = (dt.month - 1 + months) % 12 + 1
    day = min(dt.day, calendar.monthrange(year, month)[1])
    return dt.replace(year=year, month=month, day=day)


def period_end_for(start: datetime, interval: str) -> datetime:
    start = ensure_utc(start)
    if interval == BillingInterval.MONTHLY.value:
        return add_calendar_months(start, 1)
    if interval == BillingInterval.ANNUAL.value:
        return add_calendar_months(start, 12)
    raise ValueError(f"unsupported billing_interval: {interval}")
