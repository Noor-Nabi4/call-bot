"""Phase 24 Human Handoff catalogs."""

from __future__ import annotations

from enum import StrEnum

EMERGENCY_KEYWORDS: frozenset[str] = frozenset(
    {
        "water leak",
        "gas leak",
        "fire",
        "urgent",
        "flood",
        "flooding",
        "electrical issue",
        "electric shock",
        "no heat",
        "carbon monoxide",
    }
)

EMERGENCY_CONFIDENCE_THRESHOLD = 0.75

DEFAULT_DEPARTMENTS: tuple[tuple[str, str, int], ...] = (
    ("Sales", "sales", 10),
    ("Support", "support", 20),
    ("Dispatch", "dispatch", 30),
    ("Billing", "billing", 40),
    ("Emergency", "emergency", 5),
)


class HandoffChannel(StrEnum):
    VOICE = "VOICE"
    SMS = "SMS"
    CHAT = "CHAT"


class HandoffStatus(StrEnum):
    PENDING = "PENDING"
    ROUTING = "ROUTING"
    ASSIGNED = "ASSIGNED"
    CONNECTED = "CONNECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class HandoffReason(StrEnum):
    AI_REQUEST = "AI_REQUEST"
    CUSTOMER_REQUEST = "CUSTOMER_REQUEST"
    EMERGENCY = "EMERGENCY"
    AFTER_HOURS = "AFTER_HOURS"
    BUSINESS_RULE = "BUSINESS_RULE"
    MANUAL = "MANUAL"


class HandoffPriority(StrEnum):
    LOW = "LOW"
    NORMAL = "NORMAL"
    HIGH = "HIGH"
    URGENT = "URGENT"
    EMERGENCY = "EMERGENCY"


class AssignmentType(StrEnum):
    USER = "USER"
    DEPARTMENT = "DEPARTMENT"
    TECHNICIAN = "TECHNICIAN"
    QUEUE = "QUEUE"


class AssignmentStatus(StrEnum):
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REJECTED = "REJECTED"
    TIMEOUT = "TIMEOUT"


class HistoryEvent(StrEnum):
    CREATED = "CREATED"
    ROUTED = "ROUTED"
    ASSIGNED = "ASSIGNED"
    CONNECTED = "CONNECTED"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REJECTED = "REJECTED"


# Map legacy AI tool reasons → domain reasons
LEGACY_REASON_MAP: dict[str, str] = {
    "billing_dispute": HandoffReason.CUSTOMER_REQUEST.value,
    "emergency": HandoffReason.EMERGENCY.value,
    "abuse": HandoffReason.BUSINESS_RULE.value,
    "caller_request": HandoffReason.CUSTOMER_REQUEST.value,
    "complex": HandoffReason.AI_REQUEST.value,
    "other": HandoffReason.AI_REQUEST.value,
    "handoff": HandoffReason.AI_REQUEST.value,
}
