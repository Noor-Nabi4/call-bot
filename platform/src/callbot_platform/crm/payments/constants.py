"""Customer invoice payment constants (Phase 19)."""

from __future__ import annotations

from enum import Enum

PROVIDER_STRIPE = "stripe"
PURPOSE_INVOICE_PAYMENT = "invoice_payment"


class PaymentStatus(str, Enum):
    PENDING = "PENDING"
    PROCESSING = "PROCESSING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    REFUNDED = "REFUNDED"
    PARTIALLY_REFUNDED = "PARTIALLY_REFUNDED"


PAYMENT_STATUSES = frozenset(s.value for s in PaymentStatus)

REFUNDABLE_STATUSES = frozenset(
    {
        PaymentStatus.SUCCEEDED.value,
        PaymentStatus.PARTIALLY_REFUNDED.value,
    }
)
