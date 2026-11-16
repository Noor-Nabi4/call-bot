"""Jobs domain errors and shared helpers.

Checklist defaults, reference-code, and status-graph helpers now live in
``callbot_platform.crm.jobs.constants`` (Phase 10) and are re-exported here
for backward compatibility with the legacy ``/api/jobs`` repository. Do not
import ``callbot_platform.crm.jobs`` (the package, which pulls in
``JobService``) from this module — that would reintroduce the circular
import this module previously had.
"""

from __future__ import annotations

from callbot_platform.crm.jobs.constants import (
    ASSIGNABLE_STATUSES as _ASSIGNABLE,
)
from callbot_platform.crm.jobs.constants import (
    DEFAULT_CHECKLIST,
    JobStatus,
    checklist_item_id,
    job_ref,
    normalize_status,
    transitions_map,
)

# Phase 10 uppercase graph (also used by legacy /api/jobs).
TRANSITIONS: dict[str, frozenset[str]] = transitions_map()
ASSIGNABLE_STATUSES = _ASSIGNABLE


class JobsError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def coerce_status(value: str) -> str:
    try:
        return normalize_status(value)
    except ValueError as exc:
        raise JobsError("invalid_status", f"Unknown status: {value}") from exc


__all__ = [
    "ASSIGNABLE_STATUSES",
    "DEFAULT_CHECKLIST",
    "TRANSITIONS",
    "JobStatus",
    "JobsError",
    "checklist_item_id",
    "coerce_status",
    "job_ref",
    "normalize_status",
]
