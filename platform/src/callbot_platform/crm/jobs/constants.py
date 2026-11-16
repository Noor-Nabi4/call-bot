"""Job CRM domain constants (Phase 10)."""

from __future__ import annotations

import secrets
from enum import Enum


class JobStatus(str, Enum):
    NEW = "NEW"
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    DISPATCHED = "DISPATCHED"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    IN_PROGRESS = "IN_PROGRESS"
    COMPLETED = "COMPLETED"
    CANCELLED = "CANCELLED"
    NO_SHOW = "NO_SHOW"


JOB_STATUSES: frozenset[str] = frozenset(s.value for s in JobStatus)
DEFAULT_JOB_STATUS = JobStatus.NEW.value

# Authoritative transition graph. PATCH status is rejected.
# Includes operational shortcuts (DISPATCHED→IN_PROGRESS, SCHEDULED→DISPATCHED)
# so legacy dispatch/tech flows remain valid alongside the full field-service path.
VALID_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (JobStatus.NEW.value, JobStatus.SCHEDULED.value),
        (JobStatus.NEW.value, JobStatus.CANCELLED.value),
        (JobStatus.SCHEDULED.value, JobStatus.CONFIRMED.value),
        (JobStatus.SCHEDULED.value, JobStatus.DISPATCHED.value),
        (JobStatus.SCHEDULED.value, JobStatus.CANCELLED.value),
        (JobStatus.SCHEDULED.value, JobStatus.NO_SHOW.value),
        (JobStatus.CONFIRMED.value, JobStatus.DISPATCHED.value),
        (JobStatus.CONFIRMED.value, JobStatus.CANCELLED.value),
        (JobStatus.CONFIRMED.value, JobStatus.NO_SHOW.value),
        (JobStatus.DISPATCHED.value, JobStatus.EN_ROUTE.value),
        (JobStatus.DISPATCHED.value, JobStatus.IN_PROGRESS.value),
        (JobStatus.DISPATCHED.value, JobStatus.CANCELLED.value),
        (JobStatus.DISPATCHED.value, JobStatus.NO_SHOW.value),
        (JobStatus.EN_ROUTE.value, JobStatus.ARRIVED.value),
        (JobStatus.EN_ROUTE.value, JobStatus.IN_PROGRESS.value),
        (JobStatus.EN_ROUTE.value, JobStatus.CANCELLED.value),
        (JobStatus.EN_ROUTE.value, JobStatus.NO_SHOW.value),
        (JobStatus.ARRIVED.value, JobStatus.IN_PROGRESS.value),
        (JobStatus.ARRIVED.value, JobStatus.CANCELLED.value),
        (JobStatus.ARRIVED.value, JobStatus.NO_SHOW.value),
        (JobStatus.IN_PROGRESS.value, JobStatus.COMPLETED.value),
        (JobStatus.IN_PROGRESS.value, JobStatus.CANCELLED.value),
    }
)

CANCELLABLE_STATUSES: frozenset[str] = frozenset(
    {
        JobStatus.NEW.value,
        JobStatus.SCHEDULED.value,
        JobStatus.CONFIRMED.value,
        JobStatus.DISPATCHED.value,
        JobStatus.EN_ROUTE.value,
        JobStatus.ARRIVED.value,
        JobStatus.IN_PROGRESS.value,
    }
)

NO_SHOW_FROM: frozenset[str] = frozenset(
    {
        JobStatus.SCHEDULED.value,
        JobStatus.CONFIRMED.value,
        JobStatus.DISPATCHED.value,
        JobStatus.EN_ROUTE.value,
        JobStatus.ARRIVED.value,
    }
)

ASSIGNABLE_STATUSES: frozenset[str] = frozenset(
    {
        JobStatus.NEW.value,
        JobStatus.SCHEDULED.value,
        JobStatus.CONFIRMED.value,
        JobStatus.DISPATCHED.value,
    }
)

# Statuses that require an assigned technician before entering.
REQUIRES_TECHNICIAN: frozenset[str] = frozenset(
    {
        JobStatus.DISPATCHED.value,
        JobStatus.EN_ROUTE.value,
        JobStatus.ARRIVED.value,
        JobStatus.IN_PROGRESS.value,
    }
)

EDITABLE_STATUSES: frozenset[str] = frozenset(
    {
        JobStatus.NEW.value,
        JobStatus.SCHEDULED.value,
        JobStatus.CONFIRMED.value,
    }
)

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        JobStatus.COMPLETED.value,
        JobStatus.CANCELLED.value,
        JobStatus.NO_SHOW.value,
    }
)


class JobPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


JOB_PRIORITIES: frozenset[str] = frozenset(p.value for p in JobPriority)
DEFAULT_JOB_PRIORITY = JobPriority.MEDIUM.value

DESCRIPTION_MAX_LEN = 8000
NOTE_BODY_MAX_LEN = 8000
ATTACHMENT_MAX_BYTES = 15 * 1024 * 1024

_STATUS_ALIASES: dict[str, str] = {
    "NEW": JobStatus.NEW.value,
    "SCHEDULED": JobStatus.SCHEDULED.value,
    "CONFIRMED": JobStatus.CONFIRMED.value,
    "DISPATCHED": JobStatus.DISPATCHED.value,
    "EN_ROUTE": JobStatus.EN_ROUTE.value,
    "ENROUTE": JobStatus.EN_ROUTE.value,
    "ARRIVED": JobStatus.ARRIVED.value,
    "IN_PROGRESS": JobStatus.IN_PROGRESS.value,
    "INPROGRESS": JobStatus.IN_PROGRESS.value,
    "COMPLETED": JobStatus.COMPLETED.value,
    "CANCELLED": JobStatus.CANCELLED.value,
    "CANCELED": JobStatus.CANCELLED.value,
    "NO_SHOW": JobStatus.NO_SHOW.value,
    "NOSHOW": JobStatus.NO_SHOW.value,
}


def normalize_status(value: str) -> str:
    key = (value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if key not in _STATUS_ALIASES:
        raise ValueError(f"unknown_status:{value}")
    return _STATUS_ALIASES[key]


def normalize_priority(value: str | None) -> str:
    if value is None or not str(value).strip():
        return DEFAULT_JOB_PRIORITY
    key = str(value).strip().upper()
    if key not in JOB_PRIORITIES:
        raise ValueError(f"unknown_priority:{value}")
    return key


def transitions_map() -> dict[str, frozenset[str]]:
    out: dict[str, set[str]] = {s: set() for s in JOB_STATUSES}
    for src, dst in VALID_TRANSITIONS:
        out[src].add(dst)
    return {k: frozenset(v) for k, v in out.items()}


# Default checklist seeded on job creation (legacy ops UI + Phase 10 CRM share this).
DEFAULT_CHECKLIST: list[dict[str, object]] = [
    {"id": "arrive", "label": "Arrive on site", "done": False},
    {"id": "diagnose", "label": "Diagnose issue", "done": False},
    {"id": "complete_work", "label": "Complete work", "done": False},
    {"id": "customer_signoff", "label": "Customer sign-off", "done": False},
]


def job_ref() -> str:
    """Short human-friendly job reference code (distinct from job_number)."""
    return f"JOB-{secrets.token_hex(3).upper()}"


def checklist_item_id() -> str:
    return secrets.token_hex(4)
