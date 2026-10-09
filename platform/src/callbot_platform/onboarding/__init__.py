"""Organization onboarding state package."""

from __future__ import annotations

from callbot_platform.onboarding.access import (
    ONBOARDING_SATISFIED_STATUSES,
    assert_onboarding_satisfied,
    is_onboarding_satisfied,
    onboarding_status_for_tenant,
)
from callbot_platform.onboarding.errors import OnboardingError
from callbot_platform.onboarding.service import OnboardingService
from callbot_platform.onboarding.status import (
    STATUS_COMPLETED,
    STATUS_IN_PROGRESS,
    STATUS_NOT_STARTED,
    STATUS_SKIPPED,
)
from callbot_platform.onboarding.steps import ONBOARDING_STEPS, list_step_defs

__all__ = [
    "ONBOARDING_SATISFIED_STATUSES",
    "ONBOARDING_STEPS",
    "STATUS_COMPLETED",
    "STATUS_IN_PROGRESS",
    "STATUS_NOT_STARTED",
    "STATUS_SKIPPED",
    "OnboardingError",
    "OnboardingService",
    "assert_onboarding_satisfied",
    "is_onboarding_satisfied",
    "list_step_defs",
    "onboarding_status_for_tenant",
]
