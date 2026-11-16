"""Platform SaaS Stripe billing service (not Connect)."""

from __future__ import annotations

import logging
import re
import secrets
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
_SLUG_TAKEN_MESSAGE = "That business ID is already taken"
_SLUG_INVALID_MESSAGE = (
    "Business ID must be 2-64 characters: lowercase letters, numbers, hyphens"
)


class BillingService:
    """Signup, Stripe wallet top-ups, and entitlement for platform tenants."""

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

    @staticmethod
    def slugify_business_name(business_name: str) -> str:
        """Derive a workspace ID candidate from a business name."""
        cleaned = re.sub(r"[^a-z0-9]+", "-", (business_name or "").strip().lower())
        cleaned = cleaned.strip("-")[:64].strip("-")
        if len(cleaned) < 2:
            return "workspace"
        return cleaned

    def _slug_is_available(self, slug: str) -> bool:
        existing_id = self._session.scalar(
            select(Tenant.id).where(Tenant.slug == slug).limit(1)
        )
        return existing_id is None

    def _slug_field_error(self, slug: str) -> dict[str, str] | None:
        cleaned = (slug or "").strip().lower()
        if (
            not cleaned
            or not _SLUG_RE.match(cleaned)
            or len(cleaned) < 2
            or len(cleaned) > 64
        ):
            return {"code": "invalid_slug", "message": _SLUG_INVALID_MESSAGE}
        if not self._slug_is_available(cleaned):
            return {"code": "slug_taken", "message": _SLUG_TAKEN_MESSAGE}
        return None

    def allocate_signup_slug(self, business_name: str) -> str:
        """Pick a free workspace ID from the business name (never ask the user)."""
        base = self.slugify_business_name(business_name)
        if self._slug_is_available(base):
            return base
        # Collision: keep readable base + short random suffix.
        for _ in range(24):
            suffix = secrets.token_hex(3)
            candidate = f"{base[: 64 - len(suffix) - 1]}-{suffix}".strip("-")
            if (
                len(candidate) >= 2
                and _SLUG_RE.match(candidate)
                and self._slug_is_available(candidate)
            ):
                return candidate
        raise BillingError(
            "slug_taken",
            "Could not allocate a workspace ID — try a different business name",
        )

    def _email_field_error(self, email: str) -> dict[str, str] | None:
        cleaned = (email or "").strip().lower()
        if not cleaned or "@" not in cleaned or len(cleaned) > 320:
            return {
                "code": "invalid_email",
                "message": "Enter a valid work email",
            }
        local, _, domain = cleaned.partition("@")
        if not local or not domain or "." not in domain:
            return {
                "code": "invalid_email",
                "message": "Enter a valid work email",
            }
        return None

    def _plan_field_error(self, plan_key: str) -> dict[str, str] | None:
        plan = (plan_key or "").strip().lower()
        if plan not in VALID_PLAN_KEYS:
            return {
                "code": "invalid_plan",
                "message": "Choose starter, growth, or pro",
            }
        catalog_plan = plan_by_key(plan)
        if catalog_plan is None or catalog_plan.get("unit_amount") is None:
            return {
                "code": "invalid_plan",
                "message": "Plan pricing is not available",
            }
        return None

    def validate_signup_fields(
        self,
        *,
        slug: str | None = None,
        email: str | None = None,
        plan_key: str | None = None,
    ) -> dict[str, Any]:
        """Validate only the provided signup fields; return per-field errors."""
        errors: dict[str, dict[str, str]] = {}
        if slug is not None:
            slug_error = self._slug_field_error(slug)
            if slug_error is not None:
                errors["slug"] = slug_error
        if email is not None:
            email_error = self._email_field_error(email)
            if email_error is not None:
                errors["email"] = email_error
        if plan_key is not None:
            plan_error = self._plan_field_error(plan_key)
            if plan_error is not None:
                errors["plan_key"] = plan_error
        return {"ok": not errors, "errors": errors}

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
        data["is_entitled"] = self.tenant_is_entitled(tenant_id)
        return data

    def get_usage(self, tenant_id: UUID) -> dict[str, Any]:
        from callbot_platform.billing.usage import UsageService

        return UsageService(self._session).usage_summary(tenant_id)

    def tenant_is_entitled(self, tenant_id: UUID) -> bool:
        """Active/grace subscription and positive available wallet balance."""
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            return False
        row = self._repo.get_by_tenant(tenant_id)
        if row is None:
            return tenant.status == TenantStatus.ACTIVE.value
        if row.status in ACTIVE_SUBSCRIPTION_STATUSES:
            pass
        elif row.status == "past_due":
            grace_end = row.grace_period_ends_at
            if grace_end is None:
                return False
            now = datetime.now(UTC)
            end = grace_end if grace_end.tzinfo else grace_end.replace(tzinfo=UTC)
            if now >= end:
                return False
        else:
            return False
        from callbot_platform.billing.wallet.service import WalletService

        return WalletService(self._session).can_start_billable_call(tenant_id)

    def signup(
        self,
        *,
        business_name: str,
        timezone: str,
        name: str,
        email: str,
        password: str,
        plan_key: str,
        slug: str | None = None,
    ) -> dict[str, Any]:
        """
        Create pending tenant + admin + billing intent + Stripe provisioning job.

        Workspace ID is allocated from business_name (unique). Optional `slug` is
        ignored for allocation — kept for backward-compatible callers.

        No Stripe HTTP inside the open DB transaction. Caller commits, then runs
        the async job (see async_jobs.runner) to obtain checkout_url.
        """
        _ = slug  # clients no longer choose workspace ID
        self._require_stripe()
        cleaned_slug = self.allocate_signup_slug(business_name)
        validation = self.validate_signup_fields(
            email=email,
            plan_key=plan_key,
        )
        field_errors = validation["errors"]
        if "plan_key" in field_errors:
            err = field_errors["plan_key"]
            raise BillingError(err["code"], err["message"])
        if "email" in field_errors:
            err = field_errors["email"]
            raise BillingError(err["code"], err["message"])
        plan = plan_key.strip().lower()
        if len(password) < 8:
            raise AuthError("weak_password", "Password must be at least 8 characters")

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

        # Mandatory onboarding starts NOT_STARTED — never assume complete.
        from callbot_platform.onboarding.repos import OnboardingRepository

        OnboardingRepository(self._session).ensure(tenant.id)

        sub = self._repo.create_incomplete(
            tenant_id=tenant.id,
            stripe_customer_id=None,
            plan_key=plan,
            provisioning_status="pending_stripe",
        )

        from callbot_platform.async_jobs.service import AsyncJobService
        from callbot_platform.async_jobs.types import JobType

        job = AsyncJobService(self._session, settings=self._settings).enqueue(
            tenant_id=tenant.id,
            job_type=JobType.STRIPE_SIGNUP_PROVISION,
            idempotency_key=f"tenant:{tenant.id}:billing:signup",
            resource_id=str(sub.id),
            payload={
                "plan_key": plan,
                "email": email.strip().lower(),
                "business_name": business_name.strip(),
            },
        )

        write_audit(
            self._session,
            tenant_id=tenant.id,
            actor=email.strip().lower(),
            action="tenant_signup_queued",
            resource_ids={"plan_key": plan, "job_id": str(job.id)},
        )
        self._session.flush()
        return {
            "user": user,
            "checkout_url": None,
            "job_id": str(job.id),
            "tenant_id": str(tenant.id),
            "slug": cleaned_slug,
            "provisioning": "queued",
        }

    def get_signup_checkout(self, tenant_id: UUID) -> dict[str, Any]:
        row = self._repo.get_by_tenant(tenant_id)
        if row is None:
            raise BillingError("subscription_not_found", "No subscription for tenant")
        return {
            "tenant_id": str(tenant_id),
            "checkout_url": row.checkout_url,
            "provisioning_status": getattr(row, "provisioning_status", "ready"),
            "stripe_customer_id": row.stripe_customer_id,
            "status": row.status,
            "plan_key": row.plan_key,
        }

    def create_checkout_for_tenant(
        self, *, tenant_id: UUID, plan_key: str | None = None
    ) -> dict[str, Any]:
        """
        Queue Stripe checkout provisioning (no Stripe HTTP in this TX).

        Returns job_id; caller commits then runs stripe.checkout_provision.
        """
        self._require_stripe()
        row = self._repo.get_by_tenant(tenant_id)
        if row is None:
            raise BillingError(
                "subscription_not_found", "No subscription for this tenant"
            )
        if row.status not in CHECKOUT_ELIGIBLE_STATUSES:
            raise BillingError(
                "checkout_not_allowed",
                "Subscription is already active; add funds or change plan from Billing",
            )
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise BillingError("tenant_not_found", "Tenant not found")
        if not row.stripe_customer_id:
            raise BillingError(
                "customer_missing",
                "Stripe customer not provisioned yet; wait for signup job",
            )

        plan = (plan_key or row.plan_key).strip().lower()
        if plan not in VALID_PLAN_KEYS:
            raise BillingError("invalid_plan", "Choose starter, growth, or pro")
        catalog_plan = plan_by_key(plan)
        if catalog_plan is None or catalog_plan.get("unit_amount") is None:
            raise BillingError("invalid_plan", "Plan pricing is not available")
        row.plan_key = plan
        row.stripe_price_id = None
        row.provisioning_status = "pending_checkout"
        row.checkout_url = None
        self._session.flush()

        from callbot_platform.async_jobs.service import AsyncJobService
        from callbot_platform.async_jobs.types import JobType

        amount_cents = int(catalog_plan.get("unit_amount") or 10000)
        job = AsyncJobService(self._session, settings=self._settings).enqueue(
            tenant_id=tenant_id,
            job_type=JobType.STRIPE_CHECKOUT_PROVISION,
            idempotency_key=f"tenant:{tenant_id}:billing:{plan}:topup_job",
            resource_id=str(row.id),
            payload={"plan_key": plan, "amount_cents": amount_cents},
        )
        return {
            "job_id": str(job.id),
            "tenant_id": str(tenant_id),
            "checkout_url": None,
            "provisioning": "queued",
        }

    def create_portal_session(self, *, tenant_id: UUID) -> str:
        """Read subscription then call Stripe (no prior writes in this path)."""
        self._require_stripe()
        row = self._repo.get_by_tenant(tenant_id)
        if row is None:
            raise BillingError(
                "subscription_not_found", "No subscription for this tenant"
            )
        if not row.stripe_customer_id:
            raise BillingError("customer_missing", "Stripe customer not provisioned")
        customer_id = row.stripe_customer_id
        self._session.expire_all()
        try:
            portal = stripe.billing_portal.Session.create(
                customer=customer_id,
                return_url=self._settings.stripe_portal_return_url,
            )
        except stripe.error.StripeError as exc:
            logger.exception("Stripe portal session failed for tenant %s", tenant_id)
            raise BillingError("stripe_error", "Could not open billing portal") from exc
        if not portal.url:
            raise BillingError("stripe_error", "Billing portal did not return a URL")
        return portal.url

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
        elif event_type == "charge.refunded":
            from callbot_platform.billing.wallet.topup_service import WalletTopupService

            WalletTopupService(self._session, self._settings).handle_refund(data_object)
        elif event_type == "charge.dispute.created":
            self._on_dispute_created(data_object)
        elif event_type in (
            "customer.subscription.created",
            "customer.subscription.updated",
            "customer.subscription.deleted",
            "invoice.paid",
            "invoice.payment_failed",
        ):
            # Legacy Stripe subscription events ignored after wallet cutover.
            logger.info("Ignoring legacy Stripe subscription event type=%s", event_type)
        else:
            logger.info("Ignoring unhandled Stripe event type=%s", event_type)

        self._repo.mark_webhook_processed(event_id, event_type)
        self._session.flush()
        return {"ok": True, "duplicate": False}

    def _on_checkout_completed(self, session_obj: Any) -> None:
        mode = getattr(session_obj, "mode", None) or (
            session_obj.get("mode") if isinstance(session_obj, dict) else None
        )
        metadata = getattr(session_obj, "metadata", None) or (
            session_obj.get("metadata") if isinstance(session_obj, dict) else {}
        )
        purpose = ""
        if isinstance(metadata, dict):
            purpose = str(metadata.get("purpose") or "")
        if str(mode or "") == "payment" or purpose == "wallet_topup":
            from callbot_platform.billing.wallet.topup_service import WalletTopupService

            WalletTopupService(
                self._session, self._settings
            ).credit_from_checkout_session(session_obj)
            return
        logger.info("Ignoring non-wallet checkout.session.completed mode=%s", mode)

    def _on_dispute_created(self, charge_obj: Any) -> None:
        from callbot_platform.billing.wallet.service import WalletService

        customer_id = getattr(charge_obj, "customer", None) or (
            charge_obj.get("customer") if isinstance(charge_obj, dict) else None
        )
        if not customer_id:
            return
        row = self._repo.get_by_customer_id(str(customer_id))
        if row is None:
            return
        WalletService(self._session).freeze(row.tenant_id, reason="stripe_dispute")
        logger.warning("wallet frozen due to dispute tenant=%s", row.tenant_id)
