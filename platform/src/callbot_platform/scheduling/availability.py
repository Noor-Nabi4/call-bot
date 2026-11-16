"""Availability slot generation in tenant timezone."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, date, datetime, time, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

DAY_KEYS = ("mon", "tue", "wed", "thu", "fri", "sat", "sun")


@dataclass(frozen=True, slots=True)
class TimeSlot:
    starts_at: datetime  # UTC
    ends_at: datetime  # UTC
    local_start: str
    local_end: str


def resolve_tz(name: str) -> ZoneInfo:
    try:
        return ZoneInfo(name)
    except ZoneInfoNotFoundError as exc:
        raise ValueError(f"Unknown timezone: {name}") from exc


def parse_hhmm(value: str) -> time:
    """Parse an ``HH:MM`` string into a :class:`time`. Shared with CRM appointments."""
    hour, minute = value.strip().split(":")
    return time(int(hour), int(minute))


# Backwards-compatible private alias (existing call sites in this module).
_parse_hhmm = parse_hhmm


def _weekday_key(d: date) -> str:
    return DAY_KEYS[d.weekday()]


def ranges_overlap(
    a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime
) -> bool:
    """Half-open interval overlap: [start, end)."""
    return a_start < b_end and b_start < a_end


def generate_candidate_slots(
    *,
    timezone_name: str,
    weekly_hours: dict,
    slot_minutes: int,
    from_date: date,
    to_date: date,
    now_utc: datetime | None = None,
) -> list[TimeSlot]:
    """Expand weekly hours into concrete slots in [from_date, to_date] local days.

    Skips slots that start in the past relative to now_utc.
    """
    if slot_minutes <= 0:
        raise ValueError("slot_minutes must be positive")
    if to_date < from_date:
        raise ValueError("to_date must be on or after from_date")

    tz = resolve_tz(timezone_name)
    now = now_utc or datetime.now(UTC)
    if now.tzinfo is None:
        now = now.replace(tzinfo=UTC)

    step = timedelta(minutes=slot_minutes)
    slots: list[TimeSlot] = []
    day = from_date
    while day <= to_date:
        key = _weekday_key(day)
        windows = weekly_hours.get(key) or []
        for window in windows:
            if not isinstance(window, (list, tuple)) or len(window) != 2:
                continue
            start_t = _parse_hhmm(str(window[0]))
            end_t = _parse_hhmm(str(window[1]))
            cursor = datetime.combine(day, start_t, tzinfo=tz)
            window_end = datetime.combine(day, end_t, tzinfo=tz)
            while cursor + step <= window_end:
                ends = cursor + step
                starts_utc = cursor.astimezone(UTC)
                ends_utc = ends.astimezone(UTC)
                if starts_utc >= now:
                    slots.append(
                        TimeSlot(
                            starts_at=starts_utc,
                            ends_at=ends_utc,
                            local_start=cursor.isoformat(),
                            local_end=ends.isoformat(),
                        )
                    )
                cursor += step
        day += timedelta(days=1)
    return slots


def filter_free_slots(
    candidates: list[TimeSlot],
    booked: list[tuple[datetime, datetime]],
) -> list[TimeSlot]:
    free: list[TimeSlot] = []
    for slot in candidates:
        conflict = False
        for b_start, b_end in booked:
            if b_start.tzinfo is None:
                b_start = b_start.replace(tzinfo=UTC)
            if b_end.tzinfo is None:
                b_end = b_end.replace(tzinfo=UTC)
            if ranges_overlap(slot.starts_at, slot.ends_at, b_start, b_end):
                conflict = True
                break
        if not conflict:
            free.append(slot)
    return free
