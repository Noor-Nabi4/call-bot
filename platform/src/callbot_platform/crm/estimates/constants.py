"""Estimate domain constants (Phase 13)."""

from __future__ import annotations

from enum import Enum


class EstimateStatus(str, Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    VIEWED = "VIEWED"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"
    CONVERTED = "CONVERTED"


ESTIMATE_STATUSES: frozenset[str] = frozenset(s.value for s in EstimateStatus)
DEFAULT_ESTIMATE_STATUS = EstimateStatus.DRAFT.value

VALID_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (EstimateStatus.DRAFT.value, EstimateStatus.SENT.value),
        (EstimateStatus.DRAFT.value, EstimateStatus.CANCELLED.value),
        (EstimateStatus.SENT.value, EstimateStatus.VIEWED.value),
        (EstimateStatus.SENT.value, EstimateStatus.APPROVED.value),
        (EstimateStatus.SENT.value, EstimateStatus.REJECTED.value),
        (EstimateStatus.SENT.value, EstimateStatus.EXPIRED.value),
        (EstimateStatus.SENT.value, EstimateStatus.CANCELLED.value),
        (EstimateStatus.VIEWED.value, EstimateStatus.APPROVED.value),
        (EstimateStatus.VIEWED.value, EstimateStatus.REJECTED.value),
        (EstimateStatus.VIEWED.value, EstimateStatus.EXPIRED.value),
        (EstimateStatus.VIEWED.value, EstimateStatus.CANCELLED.value),
        (EstimateStatus.APPROVED.value, EstimateStatus.CONVERTED.value),
        (EstimateStatus.APPROVED.value, EstimateStatus.EXPIRED.value),
        (EstimateStatus.APPROVED.value, EstimateStatus.CANCELLED.value),
    }
)

EDITABLE_STATUSES: frozenset[str] = frozenset({EstimateStatus.DRAFT.value})

TERMINAL_STATUSES: frozenset[str] = frozenset(
    {
        EstimateStatus.REJECTED.value,
        EstimateStatus.EXPIRED.value,
        EstimateStatus.CANCELLED.value,
        EstimateStatus.CONVERTED.value,
    }
)

APPROVABLE_STATUSES: frozenset[str] = frozenset(
    {EstimateStatus.SENT.value, EstimateStatus.VIEWED.value}
)

REJECTABLE_STATUSES: frozenset[str] = frozenset(
    {EstimateStatus.SENT.value, EstimateStatus.VIEWED.value}
)


class EstimateItemType(str, Enum):
    SERVICE = "SERVICE"
    PRODUCT = "PRODUCT"
    CUSTOM = "CUSTOM"


ITEM_TYPES: frozenset[str] = frozenset(t.value for t in EstimateItemType)


class ConversionTarget(str, Enum):
    JOB = "JOB"
    ORDER = "ORDER"


CONVERSION_TARGETS: frozenset[str] = frozenset(t.value for t in ConversionTarget)

DEFAULT_CURRENCY = "USD"
SUPPORTED_CURRENCIES: frozenset[str] = frozenset({"USD", "CAD", "EUR", "GBP", "AUD"})
