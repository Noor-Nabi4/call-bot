"""Tenant automation package."""

from __future__ import annotations

from callbot_platform.automation.service import (
    VALID_ACTIONS,
    VALID_TRIGGERS,
    AutomationError,
    AutomationService,
)

__all__ = [
    "VALID_ACTIONS",
    "VALID_TRIGGERS",
    "AutomationError",
    "AutomationService",
]
