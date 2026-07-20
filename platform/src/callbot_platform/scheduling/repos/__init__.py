"""Scheduling repositories package — re-exports for import compatibility."""

from __future__ import annotations

from callbot_platform.scheduling.errors import SchedulingError
from callbot_platform.scheduling.repos.appointment_repo import AppointmentRepository
from callbot_platform.scheduling.repos.settings_repo import ScheduleSettingsRepository

__all__ = [
    "AppointmentRepository",
    "ScheduleSettingsRepository",
    "SchedulingError",
]
