"""Lead domain constants (Phase 8)."""

from __future__ import annotations

from enum import Enum


class LeadStatus(str, Enum):
    NEW = "NEW"
    QUALIFIED = "QUALIFIED"
    CONTACTED = "CONTACTED"
    BOOKED = "BOOKED"
    WON = "WON"
    LOST = "LOST"


LEAD_STATUSES: frozenset[str] = frozenset(s.value for s in LeadStatus)
DEFAULT_LEAD_STATUS = LeadStatus.NEW.value

PIPELINE_ORDER: tuple[str, ...] = (
    LeadStatus.NEW.value,
    LeadStatus.QUALIFIED.value,
    LeadStatus.CONTACTED.value,
    LeadStatus.BOOKED.value,
    LeadStatus.WON.value,
    LeadStatus.LOST.value,
)

# Explicit transition policy. Clients cannot bypass via raw PATCH.
# LOST → NEW is the documented reopen path.
VALID_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (LeadStatus.NEW.value, LeadStatus.QUALIFIED.value),
        (LeadStatus.NEW.value, LeadStatus.LOST.value),
        (LeadStatus.QUALIFIED.value, LeadStatus.CONTACTED.value),
        (LeadStatus.QUALIFIED.value, LeadStatus.LOST.value),
        (LeadStatus.CONTACTED.value, LeadStatus.BOOKED.value),
        (LeadStatus.CONTACTED.value, LeadStatus.LOST.value),
        (LeadStatus.BOOKED.value, LeadStatus.WON.value),
        (LeadStatus.BOOKED.value, LeadStatus.LOST.value),
        (LeadStatus.LOST.value, LeadStatus.NEW.value),
    }
)


class LeadPriority(str, Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"
    URGENT = "URGENT"


LEAD_PRIORITIES: frozenset[str] = frozenset(p.value for p in LeadPriority)
DEFAULT_LEAD_PRIORITY = LeadPriority.MEDIUM.value

# Legacy voice urgency → CRM priority
URGENCY_TO_PRIORITY: dict[str, str] = {
    "low": LeadPriority.LOW.value,
    "normal": LeadPriority.MEDIUM.value,
    "medium": LeadPriority.MEDIUM.value,
    "high": LeadPriority.HIGH.value,
    "urgent": LeadPriority.URGENT.value,
}


class LeadSource(str, Enum):
    PHONE = "PHONE"
    WEBSITE = "WEBSITE"
    REFERRAL = "REFERRAL"
    SOCIAL = "SOCIAL"
    EMAIL = "EMAIL"
    AD = "AD"
    WALK_IN = "WALK_IN"
    AI_AGENT = "AI_AGENT"
    OTHER = "OTHER"


LEAD_SOURCES: frozenset[str] = frozenset(s.value for s in LeadSource)
DEFAULT_LEAD_SOURCE = LeadSource.OTHER.value


class LeadActivityType(str, Enum):
    CREATED = "CREATED"
    STATUS_CHANGED = "STATUS_CHANGED"
    NOTE_ADDED = "NOTE_ADDED"
    NOTE_UPDATED = "NOTE_UPDATED"
    NOTE_DELETED = "NOTE_DELETED"
    OWNER_CHANGED = "OWNER_CHANGED"
    CUSTOMER_LINKED = "CUSTOMER_LINKED"
    SERVICE_LINKED = "SERVICE_LINKED"
    PRODUCT_LINKED = "PRODUCT_LINKED"
    CONTACTED = "CONTACTED"
    BOOKED = "BOOKED"
    WON = "WON"
    LOST = "LOST"
    CONVERTED = "CONVERTED"
    UPDATED = "UPDATED"
    ARCHIVED = "ARCHIVED"
    RESTORED = "RESTORED"


LEAD_ACTIVITY_TYPES: frozenset[str] = frozenset(a.value for a in LeadActivityType)

# Map status → activity type when transitioning into a terminal/notable state
STATUS_ACTIVITY_TYPES: dict[str, str] = {
    LeadStatus.CONTACTED.value: LeadActivityType.CONTACTED.value,
    LeadStatus.BOOKED.value: LeadActivityType.BOOKED.value,
    LeadStatus.WON.value: LeadActivityType.WON.value,
    LeadStatus.LOST.value: LeadActivityType.LOST.value,
}
