"""Jobs domain errors and shared helpers."""

from __future__ import annotations

import secrets

TRANSITIONS: dict[str, frozenset[str]] = {
    "new": frozenset({"scheduled", "canceled"}),
    "scheduled": frozenset({"dispatched", "canceled"}),
    "dispatched": frozenset({"in_progress", "scheduled", "canceled"}),
    "in_progress": frozenset({"completed", "canceled"}),
    "completed": frozenset(),
    "canceled": frozenset(),
}

ASSIGNABLE_STATUSES = frozenset({"new", "scheduled", "dispatched"})

DEFAULT_CHECKLIST = [
    {"id": "arrive", "label": "Arrive on site", "done": False},
    {"id": "diagnose", "label": "Diagnose issue", "done": False},
    {"id": "complete_work", "label": "Complete work", "done": False},
    {"id": "customer_signoff", "label": "Customer sign-off", "done": False},
]


class JobsError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def job_ref() -> str:
    return f"JOB-{secrets.token_hex(3).upper()}"


def checklist_item_id() -> str:
    return secrets.token_hex(4)
