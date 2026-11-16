"""Safe payment serialization — never expose secrets or raw Stripe objects."""

from __future__ import annotations

from typing import Any

from callbot_platform.crm.payments.money import serialize_money
from callbot_platform.db.models.payments import Payment, PaymentRefund


def serialize_payment(payment: Payment) -> dict[str, Any]:
    return {
        "id": str(payment.id),
        "tenant_id": str(payment.tenant_id),
        "invoice_id": str(payment.invoice_id),
        "customer_id": str(payment.customer_id),
        "provider": payment.provider,
        "status": payment.status,
        "amount": serialize_money(payment.amount),
        "currency": payment.currency,
        "refunded_amount": serialize_money(payment.refunded_amount),
        "payment_method_type": payment.payment_method_type,
        "description": payment.description,
        "checkout_url": payment.checkout_url,
        "provider_checkout_session_id": payment.provider_checkout_session_id,
        "provider_payment_intent_id": payment.provider_payment_intent_id,
        "applied_to_invoice": bool(payment.applied_to_invoice),
        "succeeded_at": (
            payment.succeeded_at.isoformat() if payment.succeeded_at else None
        ),
        "failed_at": payment.failed_at.isoformat() if payment.failed_at else None,
        "cancelled_at": (
            payment.cancelled_at.isoformat() if payment.cancelled_at else None
        ),
        "created_at": payment.created_at.isoformat() if payment.created_at else None,
        "updated_at": payment.updated_at.isoformat() if payment.updated_at else None,
    }


def serialize_refund(row: PaymentRefund) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "payment_id": str(row.payment_id),
        "amount": serialize_money(row.amount),
        "status": row.status,
        "provider_refund_id": row.provider_refund_id,
        "reason": row.reason,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
