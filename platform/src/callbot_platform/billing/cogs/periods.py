"""UTC period bounds for internal COGS reporting windows."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Literal

from callbot_platform.billing.usage import calendar_month_bounds

CogsPeriodKind = Literal[
    "today",
    "7d",
    "30d",
    "this_month",
    "last_month",
    "custom",
]

VALID_PERIODS: frozenset[str] = frozenset(
    {"today", "7d", "30d", "this_month", "last_month", "custom"}
)


def resolve_cogs_period(
    *,
    period: str = "this_month",
    start: datetime | None = None,
    end: datetime | None = None,
    now: datetime | None = None,
) -> tuple[datetime, datetime, str]:
    """Return [start, end) UTC bounds and normalized period kind."""
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)

    kind = (period or "this_month").strip().lower()
    if kind not in VALID_PERIODS:
        kind = "this_month"

    if kind == "custom":
        if start is None or end is None:
            raise ValueError("custom period requires start and end")
        start_u = start if start.tzinfo else start.replace(tzinfo=UTC)
        end_u = end if end.tzinfo else end.replace(tzinfo=UTC)
        start_u = start_u.astimezone(UTC)
        end_u = end_u.astimezone(UTC)
        if end_u <= start_u:
            raise ValueError("end must be after start")
        # Cap custom windows at 366 days to protect the DB.
        if end_u - start_u > timedelta(days=366):
            raise ValueError("custom period cannot exceed 366 days")
        return start_u, end_u, "custom"

    if kind == "today":
        day = datetime(moment.year, moment.month, moment.day, tzinfo=UTC)
        return day, day + timedelta(days=1), "today"

    if kind == "7d":
        end_u = moment
        return end_u - timedelta(days=7), end_u, "7d"

    if kind == "30d":
        end_u = moment
        return end_u - timedelta(days=30), end_u, "30d"

    if kind == "last_month":
        this_start, _ = calendar_month_bounds(moment)
        prev_anchor = this_start - timedelta(days=1)
        start_u, end_u = calendar_month_bounds(prev_anchor)
        return start_u, end_u, "last_month"

    # this_month
    start_u, end_u = calendar_month_bounds(moment)
    return start_u, end_u, "this_month"
