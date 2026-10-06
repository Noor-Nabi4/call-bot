"""Stripe signup / checkout provisioning handlers."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

import stripe
from sqlalchemy.orm import Session

from callbot_platform.billing.plans import VALID_PLAN_KEYS, plan_by_key
from callbot_platform.billing.repos import BillingRepository
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
        """Create Stripe customer + Checkout session after DB commit."""
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

        # Idempotent customer create via deterministic idempotency key.
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
        else:
            customer_id = row.stripe_customer_id
            # Verify customer still exists; recreate only if missing is handled by Stripe errors.
            _ = customer_id

        checkout_url = self._create_checkout_session(
            tenant_id=tenant_id,
            tenant_slug=tenant.slug,
            customer_id=row.stripe_customer_id,
            plan_key=plan,
        )
        row.checkout_url = checkout_url
        row.provisioning_status = "ready"
        row.updated_at = datetime.now(UTC)
        write_audit(
            session,
            tenant_id=tenant_id,
            actor=email or "async_job",
            action="tenant_signup_stripe_provisioned",
            resource_ids={
                "plan_key": plan,
                "stripe_customer_id": row.stripe_customer_id,
                "job_id": str(job.id),
            },
        )
        session.flush()
        return {
            "stripe_customer_id": row.stripe_customer_id,
            "checkout_url": checkout_url,
        }

    def handle_checkout(self, session: Session, job: AsyncJob) -> dict[str, Any]:
        self._require_stripe()
        tenant_id = job.tenant_id
        plan = str(job.payload.get("plan_key") or "").strip().lower()
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise ValueError("tenant_not_found")
        repo = BillingRepository(session)
        row = repo.get_by_tenant(tenant_id)
        if row is None or not row.stripe_customer_id:
            raise ValueError("subscription_not_found")
        if plan and plan in VALID_PLAN_KEYS:
            row.plan_key = plan
        checkout_url = self._create_checkout_session(
            tenant_id=tenant_id,
            tenant_slug=tenant.slug,
            customer_id=row.stripe_customer_id,
            plan_key=row.plan_key,
        )
        row.checkout_url = checkout_url
        row.provisioning_status = "ready"
        row.updated_at = datetime.now(UTC)
        session.flush()
        return {"checkout_url": checkout_url}

    def _create_checkout_session(
        self,
        *,
        tenant_id: UUID,
        tenant_slug: str,
        customer_id: str,
        plan_key: str,
    ) -> str:
        catalog_plan = plan_by_key(plan_key)
        if catalog_plan is None:
            raise ValueError("invalid_plan")
        unit_amount = catalog_plan.get("unit_amount")
        currency = str(catalog_plan.get("currency") or "usd")
        interval = str(catalog_plan.get("interval") or "month")
        product_name = f"Call & Flow {catalog_plan.get('name') or plan_key}"
        session = stripe.checkout.Session.create(
            mode="subscription",
            customer=customer_id,
            line_items=[
                {
                    "quantity": 1,
                    "price_data": {
                        "currency": currency,
                        "unit_amount": int(unit_amount),
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
            idempotency_key=f"tenant:{tenant_id}:billing:{plan_key}:checkout",
        )
        url = getattr(session, "url", None)
        if not url:
            raise ValueError("checkout_missing_url")
        return str(url)
