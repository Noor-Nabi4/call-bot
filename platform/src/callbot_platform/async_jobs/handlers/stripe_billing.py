"""Stripe signup / wallet top-up provisioning handlers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

import stripe
from sqlalchemy.orm import Session

from callbot_platform.billing.plans import VALID_PLAN_KEYS, plan_by_key
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.billing.wallet.topup_service import WalletTopupService
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.async_job import AsyncJob
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class StripeProvisionHandler:
    def __init__(self, *, settings: Settings | None = None) -> None:
        self._settings = settings or get_settings()

    def _require_stripe(self) -> None:
        if not self._settings.stripe_secret_key.strip():
            raise ValueError("stripe_not_configured")
        stripe.api_key = self._settings.stripe_secret_key

    def handle_signup(self, session: Session, job: AsyncJob) -> dict[str, Any]:
        """Create Stripe customer + wallet top-up Checkout (mode=payment)."""
        self._require_stripe()
        tenant_id = job.tenant_id
        plan = str(job.payload.get("plan_key") or "").strip().lower()
        email = str(job.payload.get("email") or "").strip().lower()
        business_name = str(job.payload.get("business_name") or "").strip()
        if plan not in VALID_PLAN_KEYS:
            raise ValueError("invalid_plan")
        catalog_plan = plan_by_key(plan)
        if catalog_plan is None or catalog_plan.get("unit_amount") is None:
            raise ValueError("invalid_plan")

        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise ValueError("tenant_not_found")

        repo = BillingRepository(session)
        row = repo.get_by_tenant(tenant_id)
        if row is None:
            raise ValueError("subscription_intent_missing")

        if not row.stripe_customer_id:
            customer = stripe.Customer.create(
                email=email,
                name=business_name or tenant.name,
                metadata={
                    "tenant_id": str(tenant_id),
                    "tenant_slug": tenant.slug,
                },
                idempotency_key=f"tenant:{tenant_id}:stripe:customer",
            )
            row.stripe_customer_id = customer.id
            session.flush()

        # Default top-up = plan monthly fee so activation can succeed after payment.
        amount_cents = int(catalog_plan["unit_amount"])
        topup = WalletTopupService(session, self._settings).create_topup_checkout(
            tenant_id=tenant_id,
            amount_cents=amount_cents,
            auto_activate_plan=True,
        )
        row.checkout_url = topup.get("checkout_url")
        row.provisioning_status = "ready"
        row.updated_at = datetime.now(UTC)
        write_audit(
            session,
            tenant_id=tenant_id,
            actor=email or "async_job",
            action="tenant_signup_wallet_topup_provisioned",
            resource_ids={
                "plan_key": plan,
                "stripe_customer_id": row.stripe_customer_id,
                "topup_id": topup.get("topup_id"),
                "job_id": str(job.id),
            },
        )
        session.flush()
        return {
            "stripe_customer_id": row.stripe_customer_id,
            "checkout_url": topup.get("checkout_url"),
            "topup_id": topup.get("topup_id"),
        }

    def handle_checkout(self, session: Session, job: AsyncJob) -> dict[str, Any]:
        """Re-provision a wallet top-up checkout for an existing tenant."""
        self._require_stripe()
        tenant_id = job.tenant_id
        plan = str(job.payload.get("plan_key") or "").strip().lower()
        amount = job.payload.get("amount_cents")
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise ValueError("tenant_not_found")
        repo = BillingRepository(session)
        row = repo.get_by_tenant(tenant_id)
        if row is None or not row.stripe_customer_id:
            raise ValueError("subscription_not_found")
        if plan and plan in VALID_PLAN_KEYS:
            row.plan_key = plan
        catalog = plan_by_key(row.plan_key)
        amount_cents = int(amount or (catalog or {}).get("unit_amount") or 10000)
        topup = WalletTopupService(session, self._settings).create_topup_checkout(
            tenant_id=tenant_id,
            amount_cents=amount_cents,
            auto_activate_plan=True,
        )
        row.checkout_url = topup.get("checkout_url")
        row.provisioning_status = "ready"
        row.updated_at = datetime.now(UTC)
        session.flush()
        return {
            "checkout_url": topup.get("checkout_url"),
            "topup_id": topup.get("topup_id"),
        }
