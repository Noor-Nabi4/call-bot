"""Platform SaaS Stripe billing service (not Connect)."""

from __future__ import annotations

import logging
import re
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.auth.repos import AuthError, AuthRepository
from callbot_platform.billing.errors import BillingError
from callbot_platform.billing.plans import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    CHECKOUT_ELIGIBLE_STATUSES,
    VALID_PLAN_KEYS,
    entitlements_for_plan,
    plan_by_key,
    pricing_meta,
    public_plans,
)
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.config import Settings
from callbot_platform.db.models import Tenant
from callbot_platform.domain.enums import TenantStatus
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)

_SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


class BillingService:
    """Stripe Checkout / Portal / webhooks for platform subscriptions."""

    def __init__(self, session: Session, settings: Settings) -> None:
        self._session = session
        self._settings = settings
        self._repo = BillingRepository(session)
        self._auth = AuthRepository(session)

    def _require_stripe(self) -> None:
        if not self._settings.stripe_secret_key.strip():
            raise BillingError(
                "stripe_not_configured",
                "STRIPE_SECRET_KEY is not configured",
            )
        stripe.api_key = self._settings.stripe_secret_key

    def list_plans(self, *, enrich_from_stripe: bool = False) -> list[dict[str, Any]]:
        # Catalog is code-owned; enrich_from_stripe is ignored (no registered Stripe Prices).
        _ = enrich_from_stripe
        return public_plans()

    def pricing_catalog(self, *, enrich_from_stripe: bool = False) -> dict[str, Any]:
        return {
            "plans": self.list_plans(enrich_from_stripe=enrich_from_stripe),
            **pricing_meta(),
        }

    def get_subscription(self, tenant_id: UUID) -> dict[str, Any] | None:
        row = self._repo.get_by_tenant(tenant_id)
        if row is None:
            return None
        data = self._repo.serialize(row)
        data["entitlements"] = entitlements_for_plan(row.plan_key)
        return data

    def get_usage(self, tenant_id: UUID) -> dict[str, Any]:
        from callbot_platform.billing.usage import UsageService

        return UsageService(self._session).usage_summary(tenant_id)

    def tenant_is_entitled(self, tenant_id: UUID) -> bool:
        """Whether the tenant may use gated ops features."""
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            return False
        row = self._repo.get_by_tenant(tenant_id)
        if row is None:
            # Legacy / bootstrap tenants created before SaaS billing.
            return tenant.status == TenantStatus.ACTIVE.value
        return row.status in ACTIVE_SUBSCRIPTION_STATUSES

    def signup(
        self,
        *,
        business_name: str,
        slug: str,
        timezone: str,
        name: str,
        email: str,
        password: str,
        plan_key: str,
    ) -> dict[str, Any]:
        """Create pending tenant + admin + Stripe customer + Checkout Session."""
        self._require_stripe()
        cleaned_slug = slug.strip().lower()
        if (
            not _SLUG_RE.match(cleaned_slug)
            or len(cleaned_slug) < 2
            or len(cleaned_slug) > 64
        ):
            raise BillingError(
                "invalid_slug",
                "Business ID must be 2-64 characters: lowercase letters, numbers, hyphens",
            )
        plan = plan_key.strip().lower()
        if plan not in VALID_PLAN_KEYS:
            raise BillingError("invalid_plan", "Choose starter, growth, or pro")
        catalog_plan = plan_by_key(plan)
        if catalog_plan is None or catalog_plan.get("unit_amount") is None:
            raise BillingError("invalid_plan", "Plan pricing is not available")
        if len(password) < 8:
            raise AuthError("weak_password", "Password must be at least 8 characters")

        existing = self._session.scalar(
            select(Tenant).where(Tenant.slug == cleaned_slug)
        )
        if existing is not None:
            raise BillingError("slug_taken", "That business ID is already taken")

        tenant = Tenant(
            name=business_name.strip(),
            slug=cleaned_slug,
            timezone=(timezone or "UTC").strip() or "UTC",
            status=TenantStatus.PENDING_SUBSCRIPTION.value,
        )
        self._session.add(tenant)
        self._session.flush()

        user = self._auth.bootstrap_admin(
            tenant_id=tenant.id,
            email=email,
            password=password,
            name=name,
            actor="signup",
        )

        try:
            customer = stripe.Customer.create(
                email=email.strip().lower(),
                name=business_name.strip(),
                metadata={
                    "tenant_id": str(tenant.id),
                    "tenant_slug": cleaned_slug,
                },
            )
        except stripe.error.StripeError as exc:
            logger.exception("Stripe customer create failed for tenant %s", tenant.id)
            raise BillingError(
                "stripe_error", "Could not create billing customer"
            ) from exc

        self._repo.create_incomplete(
            tenant_id=tenant.id,
            stripe_customer_id=customer.id,
            plan_key=plan,
        )

        checkout_url = self._create_checkout_session(
            tenant_id=tenant.id,
            tenant_slug=cleaned_slug,
            customer_id=customer.id,
            plan_key=plan,
        )

        write_audit(
            self._session,
            tenant_id=tenant.id,
            actor=email.strip().lower(),
            action="tenant_signup_started",
            resource_ids={"plan_key": plan, "stripe_customer_id": customer.id},
        )
        self._session.flush()
        return {"user": user, "checkout_url": checkout_url}

    def create_checkout_for_tenant(
        self, *, tenant_id: UUID, plan_key: str | None = None
    ) -> str:
        """Resume Checkout for incomplete/canceled subscriptions."""
        self._require_stripe()
        row = self._repo.get_by_tenant(tenant_id)
        if row is None:
            raise BillingError(
                "subscription_not_found", "No subscription for this tenant"
            )
        if row.status not in CHECKOUT_ELIGIBLE_STATUSES:
            raise BillingError(
                "checkout_not_allowed",
                "Subscription is already active; use the billing portal to change plans",
            )
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise BillingError("tenant_not_found", "Tenant not found")

        plan = (plan_key or row.plan_key).strip().lower()
        if plan not in VALID_PLAN_KEYS:
            raise BillingError("invalid_plan", "Choose starter, growth, or pro")
        catalog_plan = plan_by_key(plan)
        if catalog_plan is None or catalog_plan.get("unit_amount") is None:
            raise BillingError("invalid_plan", "Plan pricing is not available")
        row.plan_key = plan
        row.stripe_price_id = None
        self._session.flush()

        return self._create_checkout_session(
            tenant_id=tenant.id,
            tenant_slug=tenant.slug,
            customer_id=row.stripe_customer_id,
            plan_key=plan,
        )

    def create_portal_session(self, *, tenant_id: UUID) -> str:
        self._require_stripe()
        row = self._repo.get_by_tenant(tenant_id)
        if row is None:
            raise BillingError(
                "subscription_not_found", "No subscription for this tenant"
            )
        try:
            portal = stripe.billing_portal.Session.create(
                customer=row.stripe_customer_id,
                return_url=self._settings.stripe_portal_return_url,
            )
        except stripe.error.StripeError as exc:
            logger.exception("Stripe portal session failed for tenant %s", tenant_id)
            raise BillingError("stripe_error", "Could not open billing portal") from exc
        if not portal.url:
            raise BillingError("stripe_error", "Billing portal did not return a URL")
        return portal.url

    def _create_checkout_session(
        self,
        *,
        tenant_id: UUID,
        tenant_slug: str,
        customer_id: str,
        plan_key: str,
    ) -> str:
        catalog_plan = plan_by_key(plan_key)
        if catalog_plan is None or catalog_plan.get("unit_amount") is None:
            raise BillingError("invalid_plan", "Plan pricing is not available")
        currency = str(catalog_plan.get("currency") or "usd")
        interval = str(catalog_plan.get("interval") or "month")
        product_name = f"VoxPilot {catalog_plan['name']}"
        try:
            # Inline price_data — do not require Products/Prices registered in Stripe.
            session = stripe.checkout.Session.create(
                mode="subscription",
                customer=customer_id,
                line_items=[
                    {
                        "quantity": 1,
                        "price_data": {
                            "currency": currency,
                            "unit_amount": int(catalog_plan["unit_amount"]),
                            "recurring": {"interval": interval},
                            "product_data": {
                                "name": product_name,
                                "metadata": {"plan_key": plan_key},
                            },
                        },
                    }
                ],
                success_url=self._settings.stripe_checkout_success_url,
                cancel_url=self._settings.stripe_checkout_cancel_url,
                client_reference_id=str(tenant_id),
                metadata={
                    "tenant_id": str(tenant_id),
                    "tenant_slug": tenant_slug,
                    "plan_key": plan_key,
                },
                subscription_data={
                    "metadata": {
                        "tenant_id": str(tenant_id),
                        "tenant_slug": tenant_slug,
                        "plan_key": plan_key,
                    }
                },
            )
        except stripe.error.StripeError as exc:
            logger.exception("Stripe checkout session failed for tenant %s", tenant_id)
            raise BillingError("stripe_error", "Could not start checkout") from exc
        if not session.url:
            raise BillingError("stripe_error", "Checkout did not return a URL")
        return session.url

    def construct_webhook_event(
        self, payload: bytes, signature_header: str | None
    ) -> stripe.Event:
        secret = self._settings.stripe_webhook_secret.strip()
        if not secret:
            raise BillingError(
                "stripe_not_configured",
                "STRIPE_WEBHOOK_SECRET is not configured",
            )
        if not signature_header:
            raise BillingError("invalid_signature", "Missing Stripe-Signature header")
        try:
            return stripe.Webhook.construct_event(payload, signature_header, secret)
        except (ValueError, stripe.error.SignatureVerificationError) as exc:
            raise BillingError(
                "invalid_signature", "Invalid Stripe webhook signature"
            ) from exc

    def handle_webhook_event(self, event: stripe.Event) -> dict[str, Any]:
        event_id = str(event["id"])
        event_type = str(event["type"])
        if self._repo.webhook_already_processed(event_id):
            return {"ok": True, "duplicate": True}

        data_object = event["data"]["object"]

        if event_type == "checkout.session.completed":
            self._on_checkout_completed(data_object)
        elif event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
        ):
            self._on_subscription_changed(data_object)
        elif event_type in ("invoice.paid", "invoice.payment_failed"):
            self._on_invoice_event(data_object)
        else:
            logger.info("Ignoring unhandled Stripe event type=%s", event_type)

        self._repo.mark_webhook_processed(event_id, event_type)
        self._session.flush()
        return {"ok": True, "duplicate": False}

    def _on_checkout_completed(self, session_obj: Any) -> None:
        # Attach subscription id only; activation comes from subscription.* events.
        subscription_id = getattr(session_obj, "subscription", None) or (
            session_obj.get("subscription") if isinstance(session_obj, dict) else None
        )
        customer_id = getattr(session_obj, "customer", None) or (
            session_obj.get("customer") if isinstance(session_obj, dict) else None
        )
        client_ref = getattr(session_obj, "client_reference_id", None) or (
            session_obj.get("client_reference_id")
            if isinstance(session_obj, dict)
            else None
        )
        row = None
        if customer_id:
            row = self._repo.get_by_customer_id(str(customer_id))
        if row is None and client_ref:
            try:
                row = self._repo.get_by_tenant(UUID(str(client_ref)))
            except ValueError:
                row = None
        if row is None:
            logger.warning(
                "checkout.session.completed with no matching tenant customer=%s ref=%s",
                customer_id,
                client_ref,
            )
            return
        if subscription_id and not row.stripe_subscription_id:
            row.stripe_subscription_id = str(subscription_id)
            row.updated_at = datetime.now(UTC)
            self._session.flush()
        # If subscription object is already available, sync status from Stripe.
        if subscription_id:
            self._require_stripe()
            try:
                sub = stripe.Subscription.retrieve(str(subscription_id))
                self._apply_stripe_subscription(sub)
            except stripe.error.StripeError:
                logger.exception(
                    "Failed to retrieve subscription %s after checkout", subscription_id
                )

    def _on_subscription_changed(self, subscription_obj: Any) -> None:
        self._apply_stripe_subscription(subscription_obj)

    def _on_invoice_event(self, invoice_obj: Any) -> None:
        subscription_id = getattr(invoice_obj, "subscription", None) or (
            invoice_obj.get("subscription") if isinstance(invoice_obj, dict) else None
        )
        if not subscription_id:
            return
        self._require_stripe()
        try:
            sub = stripe.Subscription.retrieve(str(subscription_id))
            self._apply_stripe_subscription(sub)
        except stripe.error.StripeError:
            logger.exception(
                "Failed to refresh subscription %s from invoice event", subscription_id
            )

    def _apply_stripe_subscription(self, subscription_obj: Any) -> None:
        sub_id = str(
            getattr(subscription_obj, "id", None)
            or (
                subscription_obj.get("id") if isinstance(subscription_obj, dict) else ""
            )
        )
        customer_id = str(
            getattr(subscription_obj, "customer", None)
            or (
                subscription_obj.get("customer")
                if isinstance(subscription_obj, dict)
                else ""
            )
        )
        status = str(
            getattr(subscription_obj, "status", None)
            or (
                subscription_obj.get("status")
                if isinstance(subscription_obj, dict)
                else "incomplete"
            )
        )
        cancel_at_period_end = bool(
            getattr(subscription_obj, "cancel_at_period_end", None)
            if not isinstance(subscription_obj, dict)
            else subscription_obj.get("cancel_at_period_end", False)
        )

        items = getattr(subscription_obj, "items", None)
        if items is None and isinstance(subscription_obj, dict):
            items = subscription_obj.get("items")
        price_id = None
        if items is not None:
            data = getattr(items, "data", None)
            if data is None and isinstance(items, dict):
                data = items.get("data")
            if data:
                first = data[0]
                price = getattr(first, "price", None)
                if price is None and isinstance(first, dict):
                    price = first.get("price")
                if price is not None:
                    price_id = (
                        str(
                            getattr(price, "id", None)
                            or (price.get("id") if isinstance(price, dict) else "")
                            or ""
                        )
                        or None
                    )

        # Plan identity comes from subscription metadata (price_data Checkout).
        # Do not map Stripe Price IDs — plans are not registered in Stripe Dashboard.
        metadata = getattr(subscription_obj, "metadata", None) or (
            subscription_obj.get("metadata")
            if isinstance(subscription_obj, dict)
            else {}
        )
        plan_key = None
        if metadata:
            meta_plan = (
                metadata.get("plan_key")
                if isinstance(metadata, dict)
                else getattr(metadata, "get", lambda _k, _d=None: None)("plan_key")
            )
            if meta_plan and str(meta_plan).lower() in VALID_PLAN_KEYS:
                plan_key = str(meta_plan).lower()

        period_end = self._ts_to_dt(
            getattr(subscription_obj, "current_period_end", None)
            if not isinstance(subscription_obj, dict)
            else subscription_obj.get("current_period_end")
        )
        trial_end = self._ts_to_dt(
            getattr(subscription_obj, "trial_end", None)
            if not isinstance(subscription_obj, dict)
            else subscription_obj.get("trial_end")
        )

        row = None
        if sub_id:
            row = self._repo.get_by_subscription_id(sub_id)
        if row is None and customer_id:
            row = self._repo.get_by_customer_id(customer_id)
        if row is None and metadata:
            tid = (
                metadata.get("tenant_id")
                if isinstance(metadata, dict)
                else getattr(metadata, "get", lambda _k, _d=None: None)("tenant_id")
            )
            if tid:
                try:
                    row = self._repo.get_by_tenant(UUID(str(tid)))
                except ValueError:
                    row = None
        if row is None:
            logger.warning(
                "Subscription event with no matching tenant sub=%s customer=%s",
                sub_id,
                customer_id,
            )
            return

        self._repo.apply_subscription_state(
            row,
            plan_key=plan_key,
            status=status,
            stripe_subscription_id=sub_id or None,
            stripe_price_id=price_id,
            current_period_end=period_end,
            cancel_at_period_end=cancel_at_period_end,
            trial_end=trial_end,
        )
        write_audit(
            self._session,
            tenant_id=row.tenant_id,
            actor="stripe_webhook",
            action="subscription_updated",
            resource_ids={
                "status": status,
                "plan_key": plan_key or row.plan_key,
                "stripe_subscription_id": sub_id,
            },
        )

    @staticmethod
    def _ts_to_dt(value: Any) -> datetime | None:
        if value is None:
            return None
        try:
            return datetime.fromtimestamp(int(value), tz=UTC)
        except (TypeError, ValueError, OSError):
            return None
