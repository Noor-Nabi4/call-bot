"""Tenant SaaS subscription repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models import (
    StripeWebhookEvent,
    Tenant,
    TenantSubscription,
)
from callbot_platform.domain.enums import TenantStatus


class BillingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_by_tenant(self, tenant_id: UUID) -> TenantSubscription | None:
        return self._session.scalar(
            select(TenantSubscription).where(TenantSubscription.tenant_id == tenant_id)
        )

    def get_by_customer_id(self, stripe_customer_id: str) -> TenantSubscription | None:
        return self._session.scalar(
            select(TenantSubscription).where(
                TenantSubscription.stripe_customer_id == stripe_customer_id
            )
        )

    def get_by_subscription_id(
        self, stripe_subscription_id: str
    ) -> TenantSubscription | None:
        return self._session.scalar(
            select(TenantSubscription).where(
                TenantSubscription.stripe_subscription_id == stripe_subscription_id
            )
        )

    def create_incomplete(
        self,
        *,
        tenant_id: UUID,
        stripe_customer_id: str | None,
        plan_key: str,
        stripe_price_id: str | None = None,
        provisioning_status: str = "ready",
    ) -> TenantSubscription:
        row = TenantSubscription(
            tenant_id=tenant_id,
            stripe_customer_id=stripe_customer_id,
            plan_key=plan_key,
            status="incomplete",
            stripe_price_id=stripe_price_id,
            provisioning_status=provisioning_status,
        )
        self._session.add(row)
        self._session.flush()
        return row

    def webhook_already_processed(self, stripe_event_id: str) -> bool:
        existing = self._session.scalar(
            select(StripeWebhookEvent).where(
                StripeWebhookEvent.stripe_event_id == stripe_event_id
            )
        )
        return existing is not None

    def mark_webhook_processed(self, stripe_event_id: str, event_type: str) -> None:
        self._session.add(
            StripeWebhookEvent(
                stripe_event_id=stripe_event_id,
                event_type=event_type,
            )
        )
        self._session.flush()

    def apply_subscription_state(
        self,
        row: TenantSubscription,
        *,
        plan_key: str | None,
        status: str,
        stripe_subscription_id: str | None,
        stripe_price_id: str | None,
        current_period_end: datetime | None,
        cancel_at_period_end: bool,
        trial_end: datetime | None,
    ) -> TenantSubscription:
        if plan_key:
            row.plan_key = plan_key
        row.status = status
        if stripe_subscription_id:
            row.stripe_subscription_id = stripe_subscription_id
        if stripe_price_id:
            row.stripe_price_id = stripe_price_id
        row.current_period_end = current_period_end
        row.cancel_at_period_end = cancel_at_period_end
        row.trial_end = trial_end
        row.updated_at = datetime.now(UTC)

        tenant = self._session.get(Tenant, row.tenant_id)
        if tenant is not None:
            if status in {"trialing", "active"}:
                tenant.status = TenantStatus.ACTIVE.value
            elif status in {"canceled", "unpaid", "incomplete_expired"}:
                tenant.status = TenantStatus.SUSPENDED.value
            elif (
                status == "past_due"
                and tenant.status == TenantStatus.PENDING_SUBSCRIPTION.value
            ):
                # Keep tenant active but subscription status drives UX/gating.
                tenant.status = TenantStatus.ACTIVE.value

        self._session.flush()
        return row

    def serialize(self, row: TenantSubscription) -> dict[str, Any]:
        return {
            "tenant_id": str(row.tenant_id),
            "plan_key": row.plan_key,
            "status": row.status,
            "stripe_customer_id": row.stripe_customer_id,
            "stripe_subscription_id": row.stripe_subscription_id,
            "stripe_price_id": row.stripe_price_id,
            "current_period_end": (
                row.current_period_end.isoformat() if row.current_period_end else None
            ),
            "billing_period_start": (
                row.billing_period_start.isoformat()
                if getattr(row, "billing_period_start", None)
                else None
            ),
            "billing_period_end": (
                row.billing_period_end.isoformat()
                if getattr(row, "billing_period_end", None)
                else None
            ),
            "next_billing_at": (
                row.next_billing_at.isoformat()
                if getattr(row, "next_billing_at", None)
                else None
            ),
            "monthly_price_cents": getattr(row, "monthly_price_cents", None),
            "included_minutes": getattr(row, "included_minutes", None),
            "included_minutes_consumed": int(
                getattr(row, "included_minutes_consumed", 0) or 0
            ),
            "overage_rate_cents": getattr(row, "overage_rate_cents", None),
            "cancel_at_period_end": row.cancel_at_period_end,
            "trial_end": row.trial_end.isoformat() if row.trial_end else None,
            "grace_period_ends_at": (
                row.grace_period_ends_at.isoformat()
                if getattr(row, "grace_period_ends_at", None)
                else None
            ),
            "is_entitled": row.status in {"trialing", "active"},
            "billing_model": "wallet",
        }
