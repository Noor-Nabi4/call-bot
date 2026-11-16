"""Order domain constants (Phase 9)."""

from __future__ import annotations

from enum import Enum


class OrderStatus(str, Enum):
    DRAFT = "DRAFT"
    PENDING = "PENDING"
    CONFIRMED = "CONFIRMED"
    PROCESSING = "PROCESSING"
    SHIPPED = "SHIPPED"
    DELIVERED = "DELIVERED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"


ORDER_STATUSES: frozenset[str] = frozenset(s.value for s in OrderStatus)
DEFAULT_ORDER_STATUS = OrderStatus.DRAFT.value

# Authoritative transition graph. PATCH status is rejected.
VALID_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (OrderStatus.DRAFT.value, OrderStatus.PENDING.value),
        (OrderStatus.DRAFT.value, OrderStatus.CANCELLED.value),
        (OrderStatus.PENDING.value, OrderStatus.CONFIRMED.value),
        (OrderStatus.PENDING.value, OrderStatus.CANCELLED.value),
        (OrderStatus.CONFIRMED.value, OrderStatus.PROCESSING.value),
        (OrderStatus.CONFIRMED.value, OrderStatus.CANCELLED.value),
        (OrderStatus.PROCESSING.value, OrderStatus.SHIPPED.value),
        (OrderStatus.PROCESSING.value, OrderStatus.CANCELLED.value),
        (OrderStatus.SHIPPED.value, OrderStatus.DELIVERED.value),
        (OrderStatus.SHIPPED.value, OrderStatus.CANCELLED.value),
        (OrderStatus.DELIVERED.value, OrderStatus.REFUNDED.value),
    }
)

# Statuses where line items / money fields may still be edited.
EDITABLE_STATUSES: frozenset[str] = frozenset(
    {OrderStatus.DRAFT.value, OrderStatus.PENDING.value}
)

# Inventory side effects (documented in ORDER_INVENTORY_INTEGRATION.md).
# CONFIRMED → reserve; PROCESSING → release+sale; cancel after confirm → release;
# cancel/refund after sale → return.
STATUSES_WITH_RESERVATION: frozenset[str] = frozenset({OrderStatus.CONFIRMED.value})
STATUSES_WITH_SALE: frozenset[str] = frozenset(
    {
        OrderStatus.PROCESSING.value,
        OrderStatus.SHIPPED.value,
        OrderStatus.DELIVERED.value,
        OrderStatus.REFUNDED.value,
    }
)

DEFAULT_CURRENCY = "USD"
SUPPORTED_CURRENCIES: frozenset[str] = frozenset({"USD", "CAD", "EUR", "GBP", "AUD"})

REF_TYPE_ORDER = "order"
