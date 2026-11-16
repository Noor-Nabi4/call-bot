"""Onboarding status constants and transition helpers."""

from __future__ import annotations

from callbot_platform.onboarding.errors import OnboardingError

STATUS_NOT_STARTED = "NOT_STARTED"
STATUS_IN_PROGRESS = "IN_PROGRESS"
STATUS_COMPLETED = "COMPLETED"
STATUS_SKIPPED = "SKIPPED"

VALID_STATUSES = frozenset(
    {
        STATUS_NOT_STARTED,
        STATUS_IN_PROGRESS,
        STATUS_COMPLETED,
        STATUS_SKIPPED,
    }
)

# Allowed explicit status targets from API (not every transition).
# SKIPPED may resume into IN_PROGRESS or complete via mark_completed;
# new transitions *into* SKIPPED are rejected by the service (mandatory policy).
_ALLOWED_EXPLICIT = {
    STATUS_NOT_STARTED: frozenset({STATUS_IN_PROGRESS, STATUS_COMPLETED}),
    STATUS_IN_PROGRESS: frozenset({STATUS_COMPLETED}),
    STATUS_COMPLETED: frozenset(),
    STATUS_SKIPPED: frozenset({STATUS_IN_PROGRESS, STATUS_COMPLETED}),
}


def assert_can_mutate(status: str) -> None:
    """Only COMPLETED is closed. SKIPPED may resume under mandatory onboarding."""
    if status == STATUS_COMPLETED:
        raise OnboardingError(
            "onboarding_closed",
            "Onboarding is closed and cannot be modified",
        )


def assert_can_transition(current: str, target: str) -> None:
    if current == target:
        return
    allowed = _ALLOWED_EXPLICIT.get(current, frozenset())
    if target not in allowed:
        raise OnboardingError(
            "invalid_transition",
            f"Cannot transition onboarding from {current} to {target}",
        )
