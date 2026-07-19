"""Scheduling package: availability, appointments, notifications."""

from callbot_platform.scheduling.repos import AppointmentRepository, SchedulingError

__all__ = ["AppointmentRepository", "SchedulingError"]
