"""Invoice domain constants (Phase 18)."""

from __future__ import annotations

from enum import Enum

DEFAULT_CURRENCY = "USD"
SUPPORTED_CURRENCIES = frozenset({"USD", "CAD", "EUR", "GBP", "AUD"})

DEFAULT_INVOICE_STATUS = "DRAFT"

ITEM_TYPES = frozenset({"SERVICE", "PRODUCT", "CUSTOM"})


class InvoiceStatus(str, Enum):
    DRAFT = "DRAFT"
    SENT = "SENT"
    PARTIALLY_PAID = "PARTIALLY_PAID"
    PAID = "PAID"
    OVERDUE = "OVERDUE"
    VOID = "VOID"


INVOICE_STATUSES = frozenset(s.value for s in InvoiceStatus)

EDITABLE_STATUSES = frozenset({InvoiceStatus.DRAFT.value})

VOIDABLE_STATUSES = frozenset(
    {
        InvoiceStatus.DRAFT.value,
        InvoiceStatus.SENT.value,
        InvoiceStatus.PARTIALLY_PAID.value,
        InvoiceStatus.OVERDUE.value,
    }
)

PAYMENT_ELIGIBLE_STATUSES = frozenset(
    {
        InvoiceStatus.SENT.value,
        InvoiceStatus.PARTIALLY_PAID.value,
        InvoiceStatus.OVERDUE.value,
    }
)

VALID_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        (InvoiceStatus.DRAFT.value, InvoiceStatus.SENT.value),
        (InvoiceStatus.DRAFT.value, InvoiceStatus.VOID.value),
        (InvoiceStatus.SENT.value, InvoiceStatus.PARTIALLY_PAID.value),
        (InvoiceStatus.SENT.value, InvoiceStatus.PAID.value),
        (InvoiceStatus.SENT.value, InvoiceStatus.OVERDUE.value),
        (InvoiceStatus.SENT.value, InvoiceStatus.VOID.value),
        (InvoiceStatus.PARTIALLY_PAID.value, InvoiceStatus.PAID.value),
        (InvoiceStatus.PARTIALLY_PAID.value, InvoiceStatus.OVERDUE.value),
        (InvoiceStatus.PARTIALLY_PAID.value, InvoiceStatus.VOID.value),
        (InvoiceStatus.OVERDUE.value, InvoiceStatus.PARTIALLY_PAID.value),
        (InvoiceStatus.OVERDUE.value, InvoiceStatus.PAID.value),
        (InvoiceStatus.OVERDUE.value, InvoiceStatus.VOID.value),
    }
)
