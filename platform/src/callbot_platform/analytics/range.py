"""Tenant-local analytics date ranges."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

PRESETS = frozenset(
    {
        "today",
        "yesterday",
        "last_7_days",
        "last_30_days",
        "this_month",
        "last_month",
        "custom",
    }
)


class AnalyticsRangeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True)
class AnalyticsRange:
    """Half-open interval [starts_from, starts_to) in UTC, derived from tenant TZ."""

    starts_from: datetime
    starts_to: datetime
    timezone: str
    preset: str
    local_from_date: date
    local_to_date: date  # inclusive local end date for display

    def as_dict(self) -> dict[str, Any]:
        return {
            "from": self.starts_from.isoformat(),
            "to": self.starts_to.isoformat(),
            "timezone": self.timezone,
            "preset": self.preset,
            "local_from": self.local_from_date.isoformat(),
            "local_to": self.local_to_date.isoformat(),
            "inclusive_end_date": True,
            "bound_style": "half_open_utc",
        }


def resolve_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise AnalyticsRangeError(
            "invalid_timezone", f"Unknown timezone: {name}"
        ) from exc


def build_range(
    *,
    timezone: str,
    preset: str = "last_30_days",
    from_date: date | None = None,
    to_date: date | None = None,
    now: datetime | None = None,
) -> AnalyticsRange:
    preset_key = (preset or "last_30_days").strip().lower()
    if preset_key not in PRESETS:
        raise AnalyticsRangeError(
            "invalid_preset",
            f"Unsupported preset. Allowed: {sorted(PRESETS)}",
        )
    tz = resolve_tz((timezone or "UTC").strip() or "UTC")
    now_local = (now or datetime.now(UTC)).astimezone(tz)
    today = now_local.date()

    if preset_key == "today":
        local_from = today
        local_to = today
    elif preset_key == "yesterday":
        local_from = today - timedelta(days=1)
        local_to = local_from
    elif preset_key == "last_7_days":
        local_to = today
        local_from = today - timedelta(days=6)
    elif preset_key == "last_30_days":
        local_to = today
        local_from = today - timedelta(days=29)
    elif preset_key == "this_month":
        local_from = today.replace(day=1)
        local_to = today
    elif preset_key == "last_month":
        first_this = today.replace(day=1)
        local_to = first_this - timedelta(days=1)
        local_from = local_to.replace(day=1)
    else:  # custom
        if from_date is None or to_date is None:
            raise AnalyticsRangeError(
                "invalid_custom_range",
                "Custom range requires from_date and to_date",
            )
        if to_date < from_date:
            raise AnalyticsRangeError(
                "invalid_custom_range", "to_date must be on or after from_date"
            )
        if (to_date - from_date).days > 366:
            raise AnalyticsRangeError(
                "invalid_custom_range", "Custom range cannot exceed 366 days"
            )
        local_from = from_date
        local_to = to_date

    starts_from = datetime.combine(
        local_from, datetime.min.time(), tzinfo=tz
    ).astimezone(UTC)
    # Exclusive end = start of day after local_to
    starts_to = datetime.combine(
        local_to + timedelta(days=1), datetime.min.time(), tzinfo=tz
    ).astimezone(UTC)

    return AnalyticsRange(
        starts_from=starts_from,
        starts_to=starts_to,
        timezone=str(tz),
        preset=preset_key,
        local_from_date=local_from,
        local_to_date=local_to,
    )


def iter_local_dates(rng: AnalyticsRange) -> list[date]:
    out: list[date] = []
    cursor = rng.local_from_date
    while cursor <= rng.local_to_date:
        out.append(cursor)
        cursor += timedelta(days=1)
    return out
