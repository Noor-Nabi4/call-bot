"""Call Intelligence catalogs (Phase 23)."""

from __future__ import annotations

from enum import StrEnum


class RecordingStatus(StrEnum):
    PENDING = "PENDING"
    AVAILABLE = "AVAILABLE"
    PROCESSING = "PROCESSING"
    READY = "READY"
    FAILED = "FAILED"
    DELETED = "DELETED"
    EXPIRED = "EXPIRED"


class LifecycleStatus(StrEnum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    DELETED = "DELETED"


class ProcessingStatus(StrEnum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class Speaker(StrEnum):
    CUSTOMER = "CUSTOMER"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"
    UNKNOWN = "UNKNOWN"


class CallIntent(StrEnum):
    BOOKING = "BOOKING"
    RESCHEDULING = "RESCHEDULING"
    CANCELLATION = "CANCELLATION"
    SALES = "SALES"
    SUPPORT = "SUPPORT"
    EMERGENCY = "EMERGENCY"
    BILLING = "BILLING"
    PRODUCT_INQUIRY = "PRODUCT_INQUIRY"
    ORDER_INQUIRY = "ORDER_INQUIRY"
    SPAM = "SPAM"
    HUMAN_TRANSFER = "HUMAN_TRANSFER"
    OTHER = "OTHER"


class CallClassification(StrEnum):
    BOOKING = "BOOKING"
    RESCHEDULING = "RESCHEDULING"
    CANCELLATION = "CANCELLATION"
    SALES = "SALES"
    SUPPORT = "SUPPORT"
    EMERGENCY = "EMERGENCY"
    BILLING = "BILLING"
    PRODUCT_INQUIRY = "PRODUCT_INQUIRY"
    ORDER_INQUIRY = "ORDER_INQUIRY"
    SPAM = "SPAM"
    HUMAN_TRANSFER = "HUMAN_TRANSFER"
    OTHER = "OTHER"


class Sentiment(StrEnum):
    POSITIVE = "POSITIVE"
    NEUTRAL = "NEUTRAL"
    NEGATIVE = "NEGATIVE"
    MIXED = "MIXED"
    UNKNOWN = "UNKNOWN"


class AppointmentIntelStatus(StrEnum):
    NONE = "NONE"
    REQUESTED = "REQUESTED"
    SCHEDULED = "SCHEDULED"
    CONFIRMED = "CONFIRMED"
    RESCHEDULED = "RESCHEDULED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"
    UNKNOWN = "UNKNOWN"


class FollowUp(StrEnum):
    CALL_BACK = "CALL_BACK"
    SEND_INFORMATION = "SEND_INFORMATION"
    SEND_PAYMENT_LINK = "SEND_PAYMENT_LINK"
    FOLLOW_UP_SALES = "FOLLOW_UP_SALES"
    TECHNICIAN_FOLLOW_UP = "TECHNICIAN_FOLLOW_UP"
    CUSTOMER_ACTION_REQUIRED = "CUSTOMER_ACTION_REQUIRED"
    NONE = "NONE"


class ClassificationSource(StrEnum):
    RULE = "RULE"
    AI = "AI"
    HYBRID = "HYBRID"


# Appointment domain status → intelligence appointment_status
APPOINTMENT_STATUS_MAP: dict[str, str] = {
    "REQUESTED": AppointmentIntelStatus.REQUESTED.value,
    "SCHEDULED": AppointmentIntelStatus.SCHEDULED.value,
    "CONFIRMED": AppointmentIntelStatus.CONFIRMED.value,
    "RESCHEDULED": AppointmentIntelStatus.RESCHEDULED.value,
    "CANCELLED": AppointmentIntelStatus.CANCELLED.value,
    "COMPLETED": AppointmentIntelStatus.COMPLETED.value,
    "NO_SHOW": AppointmentIntelStatus.UNKNOWN.value,
}

MAX_IMPORTANT_NOTES = 10
MAX_NOTE_CHARS = 500
MAX_PROBLEM_CHARS = 2000
MAX_OUTCOME_CHARS = 2000
ANALYSIS_VERSION = 1
MAX_TRANSCRIBE_ATTEMPTS = 5
MAX_ANALYZE_ATTEMPTS = 5

# Provider speaker label → application speaker
SPEAKER_MAP: dict[str, str] = {
    "customer": Speaker.CUSTOMER.value,
    "caller": Speaker.CUSTOMER.value,
    "user": Speaker.CUSTOMER.value,
    "agent": Speaker.AGENT.value,
    "assistant": Speaker.AGENT.value,
    "bot": Speaker.AGENT.value,
    "ai": Speaker.AGENT.value,
    "system": Speaker.SYSTEM.value,
    "narrator": Speaker.SYSTEM.value,
}
