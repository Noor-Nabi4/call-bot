"""Appointment CRM domain constants (Phase 11)."""

from __future__ import annotations

import secrets
from enum import Enum

from callbot_platform.scheduling.availability import DAY_KEYS

__all__ = [
    "ACTIVE_BOOKING_STATUSES",
    "APPOINTMENT_PRIORITIES",
    "APPOINTMENT_STATUSES",
    "ASSIGNABLE_STATUSES",
    "CANCELLABLE_STATUSES",
    "DAY_KEYS",
    "DEFAULT_APPOINTMENT_PRIORITY",
    "DEFAULT_APPOINTMENT_STATUS",
    "DESCRIPTION_MAX_LEN",
    "EDITABLE_STATUSES",
    "NOTES_MAX_LEN",
    "REQUIRES_TECHNICIAN",
    "TERMINAL_STATUSES",
    "VALID_TRANSITIONS",
    "AppointmentPriority",
    "AppointmentStatus",
    "appointment_ref",
    "normalize_priority",
    "normalize_status",
    "transitions_map",
]


class AppointmentStatus(str, Enum):
    TENTATIVE = "TENTATIVE"
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


APPOINTMENT_STATUSES: frozenset[str] = frozenset(s.value for s in AppointmentStatus)
DEFAULT_APPOINTMENT_STATUS = AppointmentStatus.SCHEDULED.value

# Authoritative transition graph. PATCH (update) status is rejected — use
# POST /appointments/{id}/transition. Mirrors the exclusion-constraint set of
# "active" statuses in the 0041 migration (TENTATIVE/SCHEDULED/CONFIRMED/IN_PROGRESS).
VALID_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (AppointmentStatus.TENTATIVE.value, AppointmentStatus.SCHEDULED.value),
        (AppointmentStatus.TENTATIVE.value, AppointmentStatus.CONFIRMED.value),
        (AppointmentStatus.TENTATIVE.value, AppointmentStatus.CANCELLED.value),
        (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CONFIRMED.value),
        (AppointmentStatus.SCHEDULED.value, AppointmentStatus.IN_PROGRESS.value),
        (AppointmentStatus.SCHEDULED.value, AppointmentStatus.CANCELLED.value),
        (AppointmentStatus.SCHEDULED.value, AppointmentStatus.NO_SHOW.value),
        (AppointmentStatus.CONFIRMED.value, AppointmentStatus.IN_PROGRESS.value),
        (AppointmentStatus.CONFIRMED.value, AppointmentStatus.CANCELLED.value),
        (AppointmentStatus.CONFIRMED.value, AppointmentStatus.NO_SHOW.value),
        (AppointmentStatus.IN_PROGRESS.value, AppointmentStatus.COMPLETED.value),
        (AppointmentStatus.IN_PROGRESS.value, AppointmentStatus.CANCELLED.value),
    }
)

# Statuses that occupy a technician's calendar — block availability and are
# the set enforced by the PostgreSQL exclusion constraint on `appointments`.
ACTIVE_BOOKING_STATUSES: frozenset[str] = frozenset(
    {
        AppointmentStatus.TENTATIVE.value,
        AppointmentStatus.SCHEDULED.value,
        AppointmentStatus.CONFIRMED.value,
        AppointmentStatus.IN_PROGRESS.value,
    }
)

CANCELLABLE_STATUSES: frozenset[str] = frozenset(
    {
        AppointmentStatus.TENTATIVE.value,
        AppointmentStatus.SCHEDULED.value,
        AppointmentStatus.CONFIRMED.value,
        AppointmentStatus.IN_PROGRESS.value,
    }
)

ASSIGNABLE_STATUSES: frozenset[str] = frozenset(
    {
        AppointmentStatus.TENTATIVE.value,
        AppointmentStatus.SCHEDULED.value,
        AppointmentStatus.CONFIRMED.value,
    }
)

# Fields are freely editable (PATCH) only before work starts.
EDITABLE_STATUSES: frozenset[str] = frozenset(
    {
        AppointmentStatus.TENTATIVE.value,
        AppointmentStatus.SCHEDULED.value,
        AppointmentStatus.CONFIRMED.value,
    }
)

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        AppointmentStatus.COMPLETED.value,
        AppointmentStatus.CANCELLED.value,
        AppointmentStatus.NO_SHOW.value,
    }
)

# Statuses that require an assigned technician before entering.
REQUIRES_TECHNICIAN: frozenset[str] = frozenset(
    {
        AppointmentStatus.IN_PROGRESS.value,
    }
)


class AppointmentPriority(str, Enum):
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    EMERGENCY = "EMERGENCY"


APPOINTMENT_PRIORITIES: frozenset[str] = frozenset(p.value for p in AppointmentPriority)
DEFAULT_APPOINTMENT_PRIORITY = AppointmentPriority.NORMAL.value

DESCRIPTION_MAX_LEN = 8000
NOTES_MAX_LEN = 8000

# Case/alias tolerant status normalization — accepts legacy voice-booking
# lowercase values ("scheduled", "canceled") in addition to the canonical
# UPPERCASE CRM enum.
_STATUS_ALIASES: dict[str, str] = {
    "TENTATIVE": AppointmentStatus.TENTATIVE.value,
    "SCHEDULED": AppointmentStatus.SCHEDULED.value,
    "CONFIRMED": AppointmentStatus.CONFIRMED.value,
    "IN_PROGRESS": AppointmentStatus.IN_PROGRESS.value,
    "INPROGRESS": AppointmentStatus.IN_PROGRESS.value,
    "COMPLETED": AppointmentStatus.COMPLETED.value,
    "CANCELLED": AppointmentStatus.CANCELLED.value,
    "CANCELED": AppointmentStatus.CANCELLED.value,
    "NO_SHOW": AppointmentStatus.NO_SHOW.value,
    "NOSHOW": AppointmentStatus.NO_SHOW.value,
}


def normalize_status(value: str) -> str:
    key = (value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if key not in _STATUS_ALIASES:
        raise ValueError(f"unknown_status:{value}")
    return _STATUS_ALIASES[key]


def normalize_priority(value: str | None) -> str:
    if value is None or not str(value).strip():
        return DEFAULT_APPOINTMENT_PRIORITY
    key = str(value).strip().upper()
    if key not in APPOINTMENT_PRIORITIES:
        raise ValueError(f"unknown_priority:{value}")
    return key


def transitions_map() -> dict[str, frozenset[str]]:
    out: dict[str, set[str]] = {s: set() for s in APPOINTMENT_STATUSES}
    for src, dst in VALID_TRANSITIONS:
        out[src].add(dst)
    return {k: frozenset(v) for k, v in out.items()}


def appointment_ref() -> str:
    """Short human-friendly reference code (distinct from appointment_number)."""
    return f"APT-{secrets.token_hex(3).upper()}"
