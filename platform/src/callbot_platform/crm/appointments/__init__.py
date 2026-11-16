"""Appointment CRM domain (Phase 11)."""

from callbot_platform.crm.appointments.engine import AvailabilityEngine
from callbot_platform.crm.appointments.hours import BusinessHoursService
from callbot_platform.crm.appointments.service import AppointmentService
from callbot_platform.crm.appointments.technician_availability import (
    TechnicianAvailabilityService,
)

__all__ = [
    "AppointmentService",
    "AvailabilityEngine",
    "BusinessHoursService",
    "TechnicianAvailabilityService",
]
