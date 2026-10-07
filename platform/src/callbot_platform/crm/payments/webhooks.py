"""Verified Stripe webhooks for invoice payments (separate from SaaS billing)."""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.billing.repos import BillingRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.payments.constants import PURPOSE_INVOICE_PAYMENT
from callbot_platform.crm.payments.service import PaymentService
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class InvoicePaymentWebhookService:
    """Signature-verified Stripe events → PaymentService → InvoicePaymentService."""

    def __init__(self, session: Session, *, settings: Settings | None = None) -> None:
        self._session = session
        self._settings = settings or get_settings()
        self._billing_repo = BillingRepository(session)
        self._payments = PaymentService(session, settings=self._settings)

    def construct_event(
        self, payload: bytes, signature_header: str | None
    ) -> stripe.Event:
        secret = (
            self._settings.stripe_invoice_webhook_secret.strip()
            or self._settings.stripe_webhook_secret.strip()
        )
        if not secret:
            raise CrmError(
                "stripe_not_configured",
                "STRIPE_WEBHOOK_SECRET is not configured",
            )
        if not signature_header:
            raise CrmError("webhook_invalid", "Missing Stripe-Signature header")
        try:
            return stripe.Webhook.construct_event(payload, signature_header, secret)
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            logger.warning("payment.webhook_rejected reason=invalid_signature")
            raise CrmError(
                "webhook_invalid", "Invalid Stripe webhook signature"
            ) from exc

    def handle_event(self, event: stripe.Event) -> dict[str, Any]:
        event_id = str(event["id"])
        event_type = str(event["type"])
        if self._billing_repo.webhook_already_processed(event_id):
            logger.info(
                "stripe.webhook.duplicate provider_event_id=%s type=%s",
                event_id,
                event_type,
            )
            return {"ok": True, "duplicate": True}

        data_object = event["data"]["object"]
        handled = False
        try:
            if event_type == "checkout.session.completed":
                handled = self._on_checkout_completed(data_object)
            elif event_type == "payment_intent.succeeded":
                handled = self._on_payment_intent_succeeded(data_object)
            elif event_type == "payment_intent.payment_failed":
                handled = self._on_payment_intent_failed(data_object)
            elif event_type == "payment_intent.canceled":
                handled = self._on_payment_intent_canceled(data_object)
            elif event_type == "charge.refunded":
                handled = self._on_charge_refunded(data_object)
            else:
                logger.info(
                    "stripe.webhook.ignored type=%s provider_event_id=%s",
                    event_type,
                    event_id,
                )
        except CrmError:
            raise
        except Exception as exc:
            logger.exception(
                "stripe.webhook.failed provider_event_id=%s type=%s",
                event_id,
                event_type,
            )
            raise CrmError("provider_unavailable", "Webhook processing failed") from exc

        try:
            self._billing_repo.mark_webhook_processed(event_id, event_type)
            self._session.flush()
        except IntegrityError:
            self._session.rollback()
            return {"ok": True, "duplicate": True}

        logger.info(
            "stripe.webhook.processed provider_event_id=%s type=%s handled=%s",
            event_id,
            event_type,
            handled,
        )
        return {"ok": True, "duplicate": False, "handled": handled}

    def _meta(self, obj: Any) -> dict[str, str]:
        meta = getattr(obj, "metadata", None) or {}
        if hasattr(meta, "to_dict"):
            meta = meta.to_dict()
        if not isinstance(meta, dict):
            return {}
        return {str(k): str(v) for k, v in meta.items() if v is not None}

    def _ids_from_meta(self, meta: dict[str, str]) -> tuple[UUID, UUID] | None:
        if meta.get("purpose") != PURPOSE_INVOICE_PAYMENT:
            return None
        try:
            tenant_id = UUID(meta["tenant_id"])
            payment_id = UUID(meta["payment_id"])
        except (KeyError, ValueError):
            return None
        return tenant_id, payment_id

    def _on_checkout_completed(self, session_obj: Any) -> bool:
        meta = self._meta(session_obj)
        ids = self._ids_from_meta(meta)
        if ids is None:
            return False
        tenant_id, payment_id = ids
        pi = getattr(session_obj, "payment_intent", None)
        payment_status = getattr(session_obj, "payment_status", None)
        if payment_status and str(payment_status) != "paid":
            # Hosted checkout completed but not paid — wait for PI events.
            return True
        self._payments.mark_succeeded_and_apply(
            tenant_id,
            payment_id,
            provider_payment_intent_id=str(pi) if pi else None,
            actor="stripe_webhook",
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor="stripe_webhook",
            action="payment.webhook_processed",
            resource_ids={
                "payment_id": str(payment_id),
                "event": "checkout.session.completed",
            },
        )
        return True

    def _on_payment_intent_succeeded(self, pi_obj: Any) -> bool:
        meta = self._meta(pi_obj)
        ids = self._ids_from_meta(meta)
        if ids is None:
            return False
        tenant_id, payment_id = ids
        charge = None
        charges = getattr(pi_obj, "charges", None)
        if charges and getattr(charges, "data", None):
            charge = charges.data[0].id
        self._payments.mark_succeeded_and_apply(
            tenant_id,
            payment_id,
            provider_payment_intent_id=str(pi_obj.id),
            provider_charge_id=str(charge) if charge else None,
            payment_method_type=getattr(pi_obj, "payment_method_types", [None])[0]
            if getattr(pi_obj, "payment_method_types", None)
            else None,
            actor="stripe_webhook",
        )
        return True

    def _on_payment_intent_failed(self, pi_obj: Any) -> bool:
        meta = self._meta(pi_obj)
        ids = self._ids_from_meta(meta)
        if ids is None:
            return False
        tenant_id, payment_id = ids
        self._payments.mark_failed(tenant_id, payment_id)
        return True

    def _on_payment_intent_canceled(self, pi_obj: Any) -> bool:
        meta = self._meta(pi_obj)
        ids = self._ids_from_meta(meta)
        if ids is None:
            return False
        tenant_id, payment_id = ids
        self._payments.mark_cancelled(tenant_id, payment_id)
        return True

    def _on_charge_refunded(self, charge_obj: Any) -> bool:
        meta = self._meta(charge_obj)
        # Prefer payment_intent linkage.
        pi = getattr(charge_obj, "payment_intent", None)
        refunds = getattr(charge_obj, "refunds", None)
        data = getattr(refunds, "data", None) if refunds else None
        if not data:
            return False
        # Use latest refund.
        latest = data[0]
        refund_id = str(latest.id)
        amount_cents = int(latest.amount)
        tenant_id = None
        if meta.get("purpose") == PURPOSE_INVOICE_PAYMENT and meta.get("tenant_id"):
            try:
                tenant_id = UUID(meta["tenant_id"])
            except ValueError:
                tenant_id = None
        if tenant_id is None and pi:
            # Look up payment by PI across tenants is unsafe — require metadata.
            return False
        if tenant_id is None:
            return False
        result = self._payments.apply_provider_refund(
            tenant_id,
            provider_refund_id=refund_id,
            payment_intent_id=str(pi) if pi else None,
            amount_cents=amount_cents,
        )
        return result is not None
