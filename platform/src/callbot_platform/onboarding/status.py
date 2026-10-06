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
_ALLOWED_EXPLICIT = {
    STATUS_NOT_STARTED: frozenset({STATUS_IN_PROGRESS, STATUS_SKIPPED}),
    STATUS_IN_PROGRESS: frozenset({STATUS_COMPLETED, STATUS_SKIPPED}),
    STATUS_COMPLETED: frozenset(),
    STATUS_SKIPPED: frozenset(),
}


def assert_can_mutate(status: str) -> None:
    if status in {STATUS_COMPLETED, STATUS_SKIPPED}:
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
