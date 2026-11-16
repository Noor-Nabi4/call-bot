"""Membership domain constants (Phase 20)."""

from __future__ import annotations

from enum import StrEnum


class PlanStatus(StrEnum):
    DRAFT = "DRAFT"
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    ARCHIVED = "ARCHIVED"


class MembershipStatus(StrEnum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    PAST_DUE = "PAST_DUE"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"
    PAUSED = "PAUSED"


class BillingInterval(StrEnum):
    MONTHLY = "MONTHLY"
    ANNUAL = "ANNUAL"


class DiscountType(StrEnum):
    PERCENTAGE = "PERCENTAGE"
    FIXED_AMOUNT = "FIXED_AMOUNT"


class BillingPeriodStatus(StrEnum):
    PENDING = "PENDING"
    PAID = "PAID"
    VOID = "VOID"
    FAILED = "FAILED"


class MembershipEvent(StrEnum):
    SUBSCRIBED = "SUBSCRIBED"
    ACTIVATED = "ACTIVATED"
    RENEWED = "RENEWED"
    CANCELLED = "CANCELLED"
    CANCEL_SCHEDULED = "CANCEL_SCHEDULED"
    UPGRADED = "UPGRADED"
    DOWNGRADED = "DOWNGRADED"
    PLAN_CHANGE_SCHEDULED = "PLAN_CHANGE_SCHEDULED"
    EXPIRED = "EXPIRED"
    PAST_DUE = "PAST_DUE"
    PAYMENT_FAILED = "PAYMENT_FAILED"
    ENTITLEMENT_USED = "ENTITLEMENT_USED"


# Statuses that block a second open membership for the same customer.
OPEN_MEMBERSHIP_STATUSES = frozenset(
    {
        MembershipStatus.PENDING.value,
        MembershipStatus.ACTIVE.value,
        MembershipStatus.PAST_DUE.value,
        MembershipStatus.PAUSED.value,
    }
)

# Entitlements apply while membership is in these statuses.
ENTITLED_STATUSES = frozenset(
    {
        MembershipStatus.ACTIVE.value,
        MembershipStatus.PAST_DUE.value,  # grace: keep benefits until expired
    }
)

PLAN_SUBSCRIBABLE = frozenset({PlanStatus.ACTIVE.value})

# Cancel-at-period-end is the default product policy for paid memberships.
# Immediate cancel is supported only via explicit immediate=True (no auto-refund).
DEFAULT_CANCEL_AT_PERIOD_END = True

# Upgrade/downgrade: no proration — change applies at next billing period.
PLAN_CHANGE_EFFECTIVE = "next_period"
