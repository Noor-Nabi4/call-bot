"""Stripe-funded wallet top-ups (Checkout mode=payment)."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.billing.errors import BillingError
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.billing.wallet.constants import (
    MAX_TOPUP_CENTS,
    MIN_TOPUP_CENTS,
    TOPUP_PRESETS_CENTS,
    WALLET_CURRENCY,
)
from callbot_platform.billing.wallet.repos import WalletRepository
from callbot_platform.billing.wallet.service import WalletError, WalletService
from callbot_platform.config import Settings
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.wallet import WalletTopup

logger = logging.getLogger(__name__)


class WalletTopupService:
    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._wallets = WalletService(session)
        self._repo = WalletRepository(session)
        self._billing = BillingRepository(session)

    def presets(self) -> dict[str, Any]:
        return {
            "currency": WALLET_CURRENCY,
            "presets_cents": list(TOPUP_PRESETS_CENTS),
            "min_cents": MIN_TOPUP_CENTS,
            "max_cents": MAX_TOPUP_CENTS,
        }

    def create_topup_checkout(
        self,
        *,
        tenant_id: UUID,
        amount_cents: int,
        auto_activate_plan: bool = True,
    ) -> dict[str, Any]:
        if amount_cents < MIN_TOPUP_CENTS or amount_cents > MAX_TOPUP_CENTS:
            raise BillingError(
                "invalid_topup_amount",
                f"Top-up must be between ${MIN_TOPUP_CENTS / 100:.0f} and "
                f"${MAX_TOPUP_CENTS / 100:.0f}",
            )
        self._require_stripe()
        wallet = self._wallets.ensure_wallet(tenant_id)
        sub = self._billing.get_by_tenant(tenant_id)
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise BillingError("tenant_not_found", "Tenant not found")
        customer_id = sub.stripe_customer_id if sub else None
        if not customer_id:
            customer = stripe.Customer.create(
                email=None,
                name=tenant.name,
                metadata={"tenant_id": str(tenant_id), "tenant_slug": tenant.slug},
            )
            customer_id = str(customer.id)
            if sub is not None:
                sub.stripe_customer_id = customer_id
                self._session.flush()

        topup = WalletTopup(
            tenant_id=tenant_id,
            wallet_id=wallet.id,
            amount_cents=amount_cents,
            currency=WALLET_CURRENCY,
            status="PENDING",
        )
        self._session.add(topup)
        self._session.flush()

        metadata = {
            "tenant_id": str(tenant_id),
            "tenant_slug": tenant.slug,
            "wallet_topup_id": str(topup.id),
            "purpose": "wallet_topup",
            "auto_activate_plan": "1" if auto_activate_plan else "0",
        }
        if sub is not None:
            metadata["plan_key"] = sub.plan_key

        try:
            session = stripe.checkout.Session.create(
                mode="payment",
                customer=customer_id,
                line_items=[
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": "usd",
                            "unit_amount": amount_cents,
                            "product_data": {
                                "name": "Call & Flow wallet top-up",
                                "metadata": {"purpose": "wallet_topup"},
                            },
                        },
                    }
                ],
                success_url=self._settings.stripe_checkout_success_url,
                cancel_url=self._settings.stripe_checkout_cancel_url,
                client_reference_id=str(tenant_id),
                metadata=metadata,
                payment_intent_data={"metadata": metadata},
            )
        except stripe.error.StripeError as exc:
            logger.exception("wallet top-up checkout failed tenant=%s", tenant_id)
            topup.status = "FAILED"
            self._session.flush()
            raise BillingError(
                "stripe_error", "Could not start top-up checkout"
            ) from exc

        topup.stripe_checkout_session_id = str(session.id)
        topup.checkout_url = session.url
        pi = getattr(session, "payment_intent", None)
        if pi:
            topup.stripe_payment_intent_id = str(pi)
        self._session.flush()

        if sub is not None:
            sub.checkout_url = session.url
            sub.provisioning_status = "pending_topup"
            self._session.flush()

        return {
            "topup_id": str(topup.id),
            "checkout_url": session.url or "",
            "amount_cents": amount_cents,
            "status": topup.status,
        }

    def credit_from_checkout_session(self, session_obj: Any) -> dict[str, Any]:
        """Credit wallet after verified checkout.session.completed (payment mode)."""
        session_id = str(
            getattr(session_obj, "id", None)
            or (session_obj.get("id") if isinstance(session_obj, dict) else "")
        )
        metadata = getattr(session_obj, "metadata", None) or (
            session_obj.get("metadata") if isinstance(session_obj, dict) else {}
        )
        if not isinstance(metadata, dict):
            metadata = dict(metadata) if metadata else {}

        purpose = str(metadata.get("purpose") or "")
        if purpose and purpose != "wallet_topup":
            return {"ok": False, "reason": "not_wallet_topup"}

        topup = None
        if session_id:
            topup = self._repo.get_topup_by_checkout_session(session_id)
        topup_id = metadata.get("wallet_topup_id")
        if topup is None and topup_id:
            try:
                topup = self._session.get(WalletTopup, UUID(str(topup_id)))
            except ValueError:
                topup = None

        payment_status = getattr(session_obj, "payment_status", None) or (
            session_obj.get("payment_status") if isinstance(session_obj, dict) else None
        )
        if str(payment_status or "") not in {"paid", "no_payment_required"}:
            if topup is not None:
                topup.status = "FAILED"
                self._session.flush()
            return {"ok": False, "reason": "not_paid"}

        if topup is None:
            # Create topup from metadata if provisioning race.
            tenant_raw = metadata.get("tenant_id")
            amount_total = getattr(session_obj, "amount_total", None) or (
                session_obj.get("amount_total")
                if isinstance(session_obj, dict)
                else None
            )
            if not tenant_raw or not amount_total:
                logger.warning("wallet top-up checkout missing tenant/amount")
                return {"ok": False, "reason": "missing_topup"}
            tenant_id = UUID(str(tenant_raw))
            wallet = self._wallets.ensure_wallet(tenant_id)
            topup = WalletTopup(
                tenant_id=tenant_id,
                wallet_id=wallet.id,
                amount_cents=int(amount_total),
                currency=WALLET_CURRENCY,
                status="PENDING",
                stripe_checkout_session_id=session_id or None,
            )
            self._session.add(topup)
            self._session.flush()

        if topup.status == "SUCCEEDED" and topup.wallet_transaction_id is not None:
            return {"ok": True, "duplicate": True, "topup_id": str(topup.id)}

        pi = getattr(session_obj, "payment_intent", None) or (
            session_obj.get("payment_intent") if isinstance(session_obj, dict) else None
        )
        if pi:
            topup.stripe_payment_intent_id = str(pi)

        try:
            txn = self._wallets.credit(
                topup.tenant_id,
                amount_cents=int(topup.amount_cents),
                idempotency_key=f"topup:{topup.id}",
                reference_type="TOPUP",
                reference_id=str(topup.id),
                description=f"Wallet top-up ${int(topup.amount_cents) / 100:.2f}",
            )
        except WalletError as exc:
            topup.status = "FAILED"
            self._session.flush()
            raise BillingError(exc.code, str(exc)) from exc

        topup.status = "SUCCEEDED"
        topup.wallet_transaction_id = txn.id
        topup.credited_at = datetime.now(UTC)
        self._session.flush()

        auto_activate = str(metadata.get("auto_activate_plan") or "1") == "1"
        activated = False
        if auto_activate:
            from callbot_platform.billing.subscription_wallet import (
                SubscriptionWalletService,
            )

            try:
                SubscriptionWalletService(self._session).activate_from_wallet(
                    topup.tenant_id,
                    plan_key=str(metadata.get("plan_key") or "") or None,
                )
                activated = True
            except BillingError as exc:
                logger.info(
                    "top-up credited but plan not activated tenant=%s code=%s",
                    topup.tenant_id,
                    exc.code,
                )

        return {
            "ok": True,
            "duplicate": False,
            "topup_id": str(topup.id),
            "activated": activated,
        }

    def handle_refund(self, charge_obj: Any) -> dict[str, Any]:
        """Reverse a credited top-up when Stripe refunds the charge."""
        payment_intent = getattr(charge_obj, "payment_intent", None) or (
            charge_obj.get("payment_intent") if isinstance(charge_obj, dict) else None
        )
        amount_refunded = getattr(charge_obj, "amount_refunded", None) or (
            charge_obj.get("amount_refunded") if isinstance(charge_obj, dict) else None
        )
        if not payment_intent or not amount_refunded:
            return {"ok": False, "reason": "missing_fields"}
        topup = self._session.scalar(
            select(WalletTopup).where(
                WalletTopup.stripe_payment_intent_id == str(payment_intent)
            )
        )
        if topup is None:
            return {"ok": False, "reason": "topup_not_found"}
        if topup.status == "REFUNDED":
            return {"ok": True, "duplicate": True}

        refund_cents = int(amount_refunded)
        try:
            self._wallets.debit(
                topup.tenant_id,
                amount_cents=min(refund_cents, int(topup.amount_cents)),
                idempotency_key=f"topup_refund:{topup.id}:{refund_cents}",
                reference_type="REFUND",
                reference_id=str(topup.id),
                description="Stripe refund adjustment",
            )
        except WalletError:
            # If funds already spent, freeze wallet for reconciliation.
            self._wallets.freeze(topup.tenant_id, reason="refund_exceeds_balance")
            logger.warning(
                "refund exceeded available balance; wallet frozen tenant=%s",
                topup.tenant_id,
            )
        topup.status = "REFUNDED"
        self._session.flush()
        return {"ok": True, "topup_id": str(topup.id)}

    def _require_stripe(self) -> None:
        if not self._settings.stripe_secret_key.strip():
            raise BillingError(
                "stripe_not_configured",
                "STRIPE_SECRET_KEY is not configured",
            )
        stripe.api_key = self._settings.stripe_secret_key
