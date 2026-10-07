"""Payment domain — Checkout links, Stripe sync, invoice application."""

from __future__ import annotations

import hashlib
import json
import logging
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.invoices.constants import PAYMENT_ELIGIBLE_STATUSES
from callbot_platform.crm.invoices.payments import InvoicePaymentService
from callbot_platform.crm.payments.constants import (
    PROVIDER_STRIPE,
    PURPOSE_INVOICE_PAYMENT,
    REFUNDABLE_STATUSES,
    PaymentStatus,
)
from callbot_platform.crm.payments.money import (
    from_stripe_cents,
    require_money,
    serialize_money,
    to_stripe_cents,
)
from callbot_platform.crm.payments.serialize import serialize_payment, serialize_refund
from callbot_platform.db.models import Customer
from callbot_platform.db.models.invoices import Invoice
from callbot_platform.db.models.payments import Payment, PaymentRefund
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)

_MONEY_ZERO = Decimal("0.0000")


class PaymentService:
    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._invoice_payments = InvoicePaymentService(session)

    def _require_stripe(self) -> None:
        if not self._settings.stripe_secret_key.strip():
            raise CrmError(
                "stripe_not_configured",
                "STRIPE_SECRET_KEY is not configured",
            )
        stripe.api_key = self._settings.stripe_secret_key

    def _load_payment(
        self, tenant_id: UUID, payment_id: UUID, *, for_update: bool = False
    ) -> Payment:
        q = select(Payment).where(
            Payment.id == payment_id, Payment.tenant_id == tenant_id
        )
        if for_update:
            q = q.with_for_update()
        row = self._session.scalar(q)
        if row is None:
            raise CrmError("not_found", "Payment not found for tenant")
        return row

    def _load_invoice(
        self, tenant_id: UUID, invoice_id: UUID, *, for_update: bool = False
    ) -> Invoice:
        q = (
            select(Invoice)
            .where(Invoice.id == invoice_id, Invoice.tenant_id == tenant_id)
            .options(selectinload(Invoice.customer))
        )
        if for_update:
            q = q.with_for_update()
        row = self._session.scalar(q)
        if row is None:
            raise CrmError("not_found", "Invoice not found for tenant")
        return row

    def get(self, tenant_id: UUID, payment_id: UUID) -> dict[str, Any]:
        return serialize_payment(self._load_payment(tenant_id, payment_id))

    def list_for_invoice(
        self, tenant_id: UUID, invoice_id: UUID
    ) -> list[dict[str, Any]]:
        self._load_invoice(tenant_id, invoice_id)
        rows = self._session.scalars(
            select(Payment)
            .where(
                Payment.tenant_id == tenant_id,
                Payment.invoice_id == invoice_id,
            )
            .order_by(Payment.created_at.desc())
        ).all()
        return [serialize_payment(r) for r in rows]

    def create_payment_link(
        self,
        tenant_id: UUID,
        invoice_id: UUID,
        *,
        actor: str,
        amount: object | None = None,
        idempotency_key: str | None = None,
        description: str | None = None,
    ) -> dict[str, Any]:
        """Create Stripe Checkout Session for an invoice balance (or partial)."""
        self._require_stripe()
        key = idempotency_key.strip() if idempotency_key else None
        invoice = self._load_invoice(tenant_id, invoice_id, for_update=True)

        if invoice.status not in PAYMENT_ELIGIBLE_STATUSES:
            raise CrmError(
                "invoice_not_payable",
                f"Invoice status {invoice.status} is not payable",
            )
        balance = invoice.balance_due or _MONEY_ZERO
        if balance <= 0:
            raise CrmError("invoice_paid", "Invoice has no balance due")

        if amount is None:
            pay_amount = balance
        else:
            pay_amount = require_money(amount, field="amount")
            if pay_amount <= 0:
                raise CrmError("invalid_amount", "Payment amount must be positive")
            if pay_amount > balance:
                raise CrmError(
                    "payment_exceeds_balance",
                    "Payment amount exceeds balance_due",
                )

        req_hash = hashlib.sha256(
            json.dumps(
                {
                    "invoice_id": str(invoice_id),
                    "amount": serialize_money(pay_amount),
                    "currency": invoice.currency,
                },
                sort_keys=True,
            ).encode()
        ).hexdigest()

        if key:
            existing = self._session.scalar(
                select(Payment).where(
                    Payment.tenant_id == tenant_id, Payment.idempotency_key == key
                )
            )
            if existing is not None:
                if (
                    existing.idempotency_request_hash
                    and existing.idempotency_request_hash != req_hash
                ):
                    raise CrmError(
                        "idempotency_conflict",
                        "Idempotency-Key reused with a different payment payload",
                    )
                return serialize_payment(existing)

        customer = self._session.scalar(
            select(Customer).where(
                Customer.id == invoice.customer_id,
                Customer.tenant_id == tenant_id,
            )
        )
        if customer is None:
            raise CrmError("customer_not_found", "Customer not found for tenant")

        payment = Payment(
            tenant_id=tenant_id,
            invoice_id=invoice.id,
            customer_id=invoice.customer_id,
            provider=PROVIDER_STRIPE,
            amount=pay_amount,
            currency=invoice.currency,
            status=PaymentStatus.PENDING.value,
            description=description or f"Invoice {invoice.invoice_number}",
            idempotency_key=key,
            idempotency_request_hash=req_hash if key else None,
            created_by=actor,
            metadata_json={"purpose": PURPOSE_INVOICE_PAYMENT},
        )
        try:
            with self._session.begin_nested():
                self._session.add(payment)
                self._session.flush()
        except IntegrityError as exc:
            if key:
                raced = self._session.scalar(
                    select(Payment).where(
                        Payment.tenant_id == tenant_id,
                        Payment.idempotency_key == key,
                    )
                )
                if raced is not None:
                    return serialize_payment(raced)
            raise CrmError("payment_conflict", "Could not create payment") from exc

        success_url = (
            self._settings.stripe_invoice_checkout_success_url
            or self._settings.stripe_checkout_success_url
        )
        cancel_url = (
            self._settings.stripe_invoice_checkout_cancel_url
            or self._settings.stripe_checkout_cancel_url
        )
        # Ensure return URLs can include payment id for UI polling.
        if "{PAYMENT_ID}" in success_url:
            success_url = success_url.replace("{PAYMENT_ID}", str(payment.id))
        if "{INVOICE_ID}" in success_url:
            success_url = success_url.replace("{INVOICE_ID}", str(invoice.id))
        if "{PAYMENT_ID}" in cancel_url:
            cancel_url = cancel_url.replace("{PAYMENT_ID}", str(payment.id))
        if "{INVOICE_ID}" in cancel_url:
            cancel_url = cancel_url.replace("{INVOICE_ID}", str(invoice.id))

        cents = to_stripe_cents(pay_amount, currency=invoice.currency)
        stripe_idem = key or f"invoice_checkout:{tenant_id}:{payment.id}"
        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                success_url=success_url,
                cancel_url=cancel_url,
                customer_email=customer.email or None,
                line_items=[
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": invoice.currency.lower(),
                            "unit_amount": cents,
                            "product_data": {
                                "name": f"Invoice {invoice.invoice_number}",
                                "description": (
                                    payment.description or "Invoice payment"
                                )[:500],
                            },
                        },
                    }
                ],
                metadata={
                    "purpose": PURPOSE_INVOICE_PAYMENT,
                    "tenant_id": str(tenant_id),
                    "invoice_id": str(invoice.id),
                    "payment_id": str(payment.id),
                    "customer_id": str(invoice.customer_id),
                },
                payment_intent_data={
                    "metadata": {
                        "purpose": PURPOSE_INVOICE_PAYMENT,
                        "tenant_id": str(tenant_id),
                        "invoice_id": str(invoice.id),
                        "payment_id": str(payment.id),
                    }
                },
                idempotency_key=stripe_idem,
            )
        except stripe.error.StripeError as exc:
            logger.exception(
                "stripe.checkout.create_failed tenant_id=%s payment_id=%s",
                tenant_id,
                payment.id,
            )
            payment.status = PaymentStatus.FAILED.value
            payment.failed_at = datetime.now(UTC)
            self._session.flush()
            raise CrmError("provider_unavailable", "Could not create checkout") from exc

        payment.provider_checkout_session_id = session.id
        payment.checkout_url = session.url
        payment.status = PaymentStatus.PROCESSING.value
        if getattr(session, "payment_intent", None):
            payment.provider_payment_intent_id = str(session.payment_intent)
        payment.updated_at = datetime.now(UTC)
        self._session.flush()

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="payment.created",
            resource_ids={
                "payment_id": str(payment.id),
                "invoice_id": str(invoice.id),
                "checkout_session_id": session.id,
            },
            idempotency_key=key,
            payload_summary={
                "amount": serialize_money(pay_amount),
                "currency": invoice.currency,
            },
        )
        logger.info(
            "stripe.checkout.create tenant_id=%s payment_id=%s amount=%s",
            tenant_id,
            payment.id,
            serialize_money(pay_amount),
        )
        return serialize_payment(payment)

    def mark_succeeded_and_apply(
        self,
        tenant_id: UUID,
        payment_id: UUID,
        *,
        provider_payment_intent_id: str | None = None,
        provider_charge_id: str | None = None,
        payment_method_type: str | None = None,
        actor: str = "stripe_webhook",
    ) -> dict[str, Any]:
        payment = self._load_payment(tenant_id, payment_id, for_update=True)
        if (
            payment.status
            in {
                PaymentStatus.SUCCEEDED.value,
                PaymentStatus.REFUNDED.value,
                PaymentStatus.PARTIALLY_REFUNDED.value,
            }
            and payment.applied_to_invoice
        ):
            return serialize_payment(payment)

        invoice = self._load_invoice(tenant_id, payment.invoice_id, for_update=True)
        # Revalidate: do not over-apply if balance already consumed.
        balance = invoice.balance_due or _MONEY_ZERO
        apply_amount = payment.amount
        if payment.applied_to_invoice:
            return serialize_payment(payment)
        if balance <= 0:
            logger.warning(
                "payment_balance_already_zero tenant_id=%s payment_id=%s",
                tenant_id,
                payment_id,
            )
            payment.status = PaymentStatus.SUCCEEDED.value
            payment.succeeded_at = datetime.now(UTC)
            payment.updated_at = datetime.now(UTC)
            self._session.flush()
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="payment.succeeded",
                resource_ids={
                    "payment_id": str(payment.id),
                    "invoice_id": str(invoice.id),
                    "note": "balance_already_zero_not_applied",
                },
            )
            return serialize_payment(payment)
        if apply_amount > balance:
            apply_amount = balance

        if provider_payment_intent_id:
            payment.provider_payment_intent_id = provider_payment_intent_id
        if provider_charge_id:
            payment.provider_charge_id = provider_charge_id
        if payment_method_type:
            payment.payment_method_type = payment_method_type[:64]

        payment.status = PaymentStatus.SUCCEEDED.value
        payment.succeeded_at = datetime.now(UTC)
        payment.updated_at = datetime.now(UTC)
        self._session.flush()

        self._invoice_payments.record_payment(
            tenant_id,
            payment.invoice_id,
            amount=apply_amount,
            actor=actor,
            payment_id=payment.id,
            idempotency_key=f"invoice_apply:{payment.id}",
            reference_note="stripe_payment",
        )
        payment.applied_to_invoice = True
        self._session.flush()

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="payment.succeeded",
            resource_ids={
                "payment_id": str(payment.id),
                "invoice_id": str(payment.invoice_id),
            },
            payload_summary={"amount": serialize_money(apply_amount)},
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="payment.applied_to_invoice",
            resource_ids={
                "payment_id": str(payment.id),
                "invoice_id": str(payment.invoice_id),
            },
        )
        return serialize_payment(payment)

    def mark_failed(
        self, tenant_id: UUID, payment_id: UUID, *, actor: str = "stripe_webhook"
    ) -> dict[str, Any]:
        payment = self._load_payment(tenant_id, payment_id, for_update=True)
        if payment.status in {
            PaymentStatus.SUCCEEDED.value,
            PaymentStatus.REFUNDED.value,
            PaymentStatus.PARTIALLY_REFUNDED.value,
        }:
            return serialize_payment(payment)
        payment.status = PaymentStatus.FAILED.value
        payment.failed_at = datetime.now(UTC)
        payment.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="payment.failed",
            resource_ids={"payment_id": str(payment.id)},
        )
        return serialize_payment(payment)

    def mark_cancelled(
        self, tenant_id: UUID, payment_id: UUID, *, actor: str = "stripe_webhook"
    ) -> dict[str, Any]:
        payment = self._load_payment(tenant_id, payment_id, for_update=True)
        if payment.status == PaymentStatus.SUCCEEDED.value:
            return serialize_payment(payment)
        payment.status = PaymentStatus.CANCELLED.value
        payment.cancelled_at = datetime.now(UTC)
        payment.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="payment.cancelled",
            resource_ids={"payment_id": str(payment.id)},
        )
        return serialize_payment(payment)

    def request_refund(
        self,
        tenant_id: UUID,
        payment_id: UUID,
        *,
        actor: str,
        amount: object | None = None,
        reason: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        self._require_stripe()
        key = idempotency_key.strip() if idempotency_key else None
        if key:
            existing = self._session.scalar(
                select(PaymentRefund).where(
                    PaymentRefund.tenant_id == tenant_id,
                    PaymentRefund.idempotency_key == key,
                )
            )
            if existing is not None:
                payment = self._load_payment(tenant_id, existing.payment_id)
                return {
                    "payment": serialize_payment(payment),
                    "refund": serialize_refund(existing),
                }

        payment = self._load_payment(tenant_id, payment_id, for_update=True)
        if payment.status not in REFUNDABLE_STATUSES:
            raise CrmError(
                "payment_not_refundable",
                f"Payment status {payment.status} is not refundable",
            )
        refundable = payment.amount - (payment.refunded_amount or _MONEY_ZERO)
        if refundable <= 0:
            raise CrmError("payment_not_refundable", "Nothing left to refund")

        if amount is None:
            refund_amount = refundable
        else:
            refund_amount = require_money(amount, field="amount")
            if refund_amount <= 0:
                raise CrmError("invalid_amount", "Refund amount must be positive")
            if refund_amount > refundable:
                raise CrmError(
                    "refund_exceeds_paid",
                    "Refund amount exceeds refundable balance",
                )

        if not payment.provider_payment_intent_id and not payment.provider_charge_id:
            raise CrmError(
                "payment_not_refundable",
                "Missing Stripe payment intent for refund",
            )

        refund_row = PaymentRefund(
            tenant_id=tenant_id,
            payment_id=payment.id,
            amount=refund_amount,
            status="PENDING",
            idempotency_key=key,
            reason=(reason.strip()[:500] if reason else None),
            created_by=actor,
        )
        self._session.add(refund_row)
        self._session.flush()

        stripe_idem = key or f"payment_refund:{tenant_id}:{refund_row.id}"
        try:
            create_kwargs: dict[str, Any] = {
                "amount": to_stripe_cents(refund_amount, currency=payment.currency),
                "idempotency_key": stripe_idem,
            }
            if payment.provider_payment_intent_id:
                create_kwargs["payment_intent"] = payment.provider_payment_intent_id
            else:
                create_kwargs["charge"] = payment.provider_charge_id
            stripe_refund = stripe.Refund.create(**create_kwargs)
        except stripe.error.StripeError as exc:
            refund_row.status = "FAILED"
            self._session.flush()
            logger.exception(
                "stripe.refund.create_failed tenant_id=%s payment_id=%s",
                tenant_id,
                payment_id,
            )
            raise CrmError("provider_unavailable", "Could not create refund") from exc

        refund_row.provider_refund_id = stripe_refund.id
        refund_status = str(getattr(stripe_refund, "status", "") or "")
        if refund_status in {"succeeded", "pending"}:
            # Treat succeeded immediately; pending confirmed via webhook.
            if refund_status == "succeeded":
                self._apply_refund_locally(
                    payment,
                    refund_row,
                    actor=actor,
                )
            else:
                refund_row.status = "PENDING"
                self._session.flush()
        else:
            refund_row.status = "FAILED"
            self._session.flush()

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="payment.refund_requested",
            resource_ids={
                "payment_id": str(payment.id),
                "refund_id": str(refund_row.id),
                "provider_refund_id": refund_row.provider_refund_id,
            },
            idempotency_key=key,
            payload_summary={"amount": serialize_money(refund_amount)},
        )
        payment = self._load_payment(tenant_id, payment_id)
        return {
            "payment": serialize_payment(payment),
            "refund": serialize_refund(refund_row),
        }

    def _apply_refund_locally(
        self, payment: Payment, refund_row: PaymentRefund, *, actor: str
    ) -> None:
        if refund_row.status == "SUCCEEDED":
            return
        payment.refunded_amount = (payment.refunded_amount or _MONEY_ZERO) + (
            refund_row.amount
        )
        if payment.refunded_amount >= payment.amount:
            payment.status = PaymentStatus.REFUNDED.value
        else:
            payment.status = PaymentStatus.PARTIALLY_REFUNDED.value
        payment.updated_at = datetime.now(UTC)
        refund_row.status = "SUCCEEDED"
        self._session.flush()

        self._invoice_payments.reverse_payment(
            payment.tenant_id,
            payment.invoice_id,
            amount=refund_row.amount,
            actor=actor,
            payment_id=payment.id,
            idempotency_key=f"invoice_refund:{refund_row.id}",
            reference_note="stripe_refund",
        )
        write_audit(
            self._session,
            tenant_id=payment.tenant_id,
            actor=actor,
            action=(
                "payment.refunded"
                if payment.status == PaymentStatus.REFUNDED.value
                else "payment.partially_refunded"
            ),
            resource_ids={
                "payment_id": str(payment.id),
                "refund_id": str(refund_row.id),
            },
        )

    def apply_provider_refund(
        self,
        tenant_id: UUID,
        *,
        provider_refund_id: str,
        payment_intent_id: str | None,
        amount_cents: int,
        actor: str = "stripe_webhook",
    ) -> dict[str, Any] | None:
        payment = None
        if payment_intent_id:
            payment = self._session.scalar(
                select(Payment)
                .where(
                    Payment.tenant_id == tenant_id,
                    Payment.provider_payment_intent_id == payment_intent_id,
                )
                .with_for_update()
            )
        if payment is None:
            return None

        existing = self._session.scalar(
            select(PaymentRefund).where(
                PaymentRefund.tenant_id == tenant_id,
                PaymentRefund.provider_refund_id == provider_refund_id,
            )
        )
        if existing is not None and existing.status == "SUCCEEDED":
            return serialize_payment(payment)

        amount = from_stripe_cents(amount_cents)
        if existing is None:
            existing = PaymentRefund(
                tenant_id=tenant_id,
                payment_id=payment.id,
                amount=amount,
                status="PENDING",
                provider_refund_id=provider_refund_id,
                created_by=actor,
            )
            self._session.add(existing)
            self._session.flush()
        self._apply_refund_locally(payment, existing, actor=actor)
        return serialize_payment(payment)
