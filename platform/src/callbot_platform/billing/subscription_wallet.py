"""Activate / renew / change plans by debiting the internal USD wallet."""

from __future__ import annotations

import calendar
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.billing.errors import BillingError
from callbot_platform.billing.plans import (
    ACTIVE_SUBSCRIPTION_STATUSES,
    VALID_PLAN_KEYS,
    entitlements_for_plan,
    plan_by_key,
)
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.billing.wallet.constants import GRACE_PERIOD_DAYS
from callbot_platform.billing.wallet.service import WalletError, WalletService
from callbot_platform.db.models import Tenant
from callbot_platform.domain.enums import TenantStatus
from callbot_platform.telephony.audit import write_audit


def utc_month_bounds(moment: datetime | None = None) -> tuple[datetime, datetime]:
    now = moment or datetime.now(UTC)
    now = now.replace(tzinfo=UTC) if now.tzinfo is None else now.astimezone(UTC)
    start = datetime(now.year, now.month, 1, tzinfo=UTC)
    if now.month == 12:
        end = datetime(now.year + 1, 1, 1, tzinfo=UTC)
    else:
        end = datetime(now.year, now.month + 1, 1, tzinfo=UTC)
    return start, end


def prorate_cents(monthly_cents: int, *, now: datetime | None = None) -> int:
    """Charge remaining fraction of the UTC calendar month (ceil to cent)."""
    moment = now or datetime.now(UTC)
    if moment.tzinfo is None:
        moment = moment.replace(tzinfo=UTC)
    else:
        moment = moment.astimezone(UTC)
    days_in_month = calendar.monthrange(moment.year, moment.month)[1]
    remaining_days = days_in_month - moment.day + 1
    if remaining_days >= days_in_month:
        return int(monthly_cents)
    return max(
        1, (int(monthly_cents) * remaining_days + days_in_month - 1) // days_in_month
    )


class SubscriptionWalletService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._repo = BillingRepository(session)
        self._wallets = WalletService(session)

    def activate_from_wallet(
        self,
        tenant_id: UUID,
        *,
        plan_key: str | None = None,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        moment = now or datetime.now(UTC)
        row = self._repo.get_by_tenant(tenant_id)
        if row is None:
            raise BillingError("subscription_not_found", "No subscription for tenant")
        if row.status in ACTIVE_SUBSCRIPTION_STATUSES:
            return self._repo.serialize(row)

        plan = (plan_key or row.plan_key).strip().lower()
        if plan not in VALID_PLAN_KEYS:
            raise BillingError("invalid_plan", "Choose starter, growth, or pro")
        catalog = plan_by_key(plan)
        if catalog is None or catalog.get("unit_amount") is None:
            raise BillingError("invalid_plan", "Plan pricing is not available")

        monthly = int(catalog["unit_amount"])
        charge = prorate_cents(monthly, now=moment)
        entitlements = entitlements_for_plan(plan) or {}
        included = int(entitlements.get("monthly_minutes") or 0)
        overage = int(catalog.get("overage_per_minute_cents") or 0)
        period_start, period_end = utc_month_bounds(moment)

        try:
            self._wallets.debit(
                tenant_id,
                amount_cents=charge,
                idempotency_key=f"sub_activate:{tenant_id}:{plan}:{period_start.date().isoformat()}",
                reference_type="SUBSCRIPTION",
                reference_id=str(row.id),
                description=f"{catalog['name']} subscription (prorated)",
            )
        except WalletError as exc:
            raise BillingError(exc.code, str(exc)) from exc

        row.plan_key = plan
        row.status = "active"
        row.monthly_price_cents = monthly
        row.included_minutes = included
        row.overage_rate_cents = overage
        row.included_minutes_consumed = 0
        row.billing_period_start = period_start
        row.billing_period_end = period_end
        row.current_period_end = period_end
        row.next_billing_at = period_end
        row.grace_period_ends_at = None
        row.provisioning_status = "ready"
        row.cancel_at_period_end = False
        row.updated_at = moment

        tenant = self._session.get(Tenant, tenant_id)
        if tenant is not None and tenant.status != TenantStatus.ACTIVE.value:
            tenant.status = TenantStatus.ACTIVE.value

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor="wallet_billing",
            action="subscription_activated_wallet",
            resource_ids={"plan_key": plan, "charged_cents": charge},
        )
        self._session.flush()
        return self._repo.serialize(row)

    def renew_due(
        self, *, now: datetime | None = None, limit: int = 100
    ) -> dict[str, Any]:
        """Renew subscriptions whose next_billing_at is due."""
        moment = now or datetime.now(UTC)
        from sqlalchemy import select

        from callbot_platform.db.models.billing import TenantSubscription

        due = list(
            self._session.scalars(
                select(TenantSubscription)
                .where(
                    TenantSubscription.status.in_(["active", "past_due"]),
                    TenantSubscription.next_billing_at.is_not(None),
                    TenantSubscription.next_billing_at <= moment,
                    TenantSubscription.cancel_at_period_end.is_(False),
                )
                .limit(limit)
            ).all()
        )
        renewed = 0
        past_due = 0
        suspended = 0
        for row in due:
            result = self._renew_one(row, moment=moment)
            if result == "renewed":
                renewed += 1
            elif result == "past_due":
                past_due += 1
            elif result == "suspended":
                suspended += 1
        return {
            "renewed": renewed,
            "past_due": past_due,
            "suspended": suspended,
            "examined": len(due),
        }

    def _renew_one(self, row: Any, *, moment: datetime) -> str:
        catalog = plan_by_key(row.plan_key)
        if catalog is None or catalog.get("unit_amount") is None:
            return "skipped"
        monthly = int(row.monthly_price_cents or catalog["unit_amount"])
        period_start, period_end = utc_month_bounds(moment)
        try:
            self._wallets.debit(
                row.tenant_id,
                amount_cents=monthly,
                idempotency_key=f"sub_renew:{row.tenant_id}:{period_start.date().isoformat()}",
                reference_type="SUBSCRIPTION",
                reference_id=str(row.id),
                description=f"{catalog['name']} monthly renewal",
            )
        except WalletError:
            if row.status != "past_due":
                row.status = "past_due"
                row.grace_period_ends_at = moment + timedelta(days=GRACE_PERIOD_DAYS)
                self._session.flush()
                return "past_due"
            if row.grace_period_ends_at and moment >= row.grace_period_ends_at:
                row.status = "suspended"
                tenant = self._session.get(Tenant, row.tenant_id)
                if tenant is not None:
                    tenant.status = TenantStatus.SUSPENDED.value
                write_audit(
                    self._session,
                    tenant_id=row.tenant_id,
                    actor="wallet_billing",
                    action="subscription_suspended_insufficient_funds",
                    resource_ids={"plan_key": row.plan_key},
                )
                self._session.flush()
                return "suspended"
            return "past_due"

        entitlements = entitlements_for_plan(row.plan_key) or {}
        row.status = "active"
        row.billing_period_start = period_start
        row.billing_period_end = period_end
        row.current_period_end = period_end
        row.next_billing_at = period_end
        row.included_minutes = int(
            entitlements.get("monthly_minutes") or row.included_minutes or 0
        )
        row.included_minutes_consumed = 0
        row.grace_period_ends_at = None
        row.updated_at = moment
        tenant = self._session.get(Tenant, row.tenant_id)
        if tenant is not None and tenant.status != TenantStatus.ACTIVE.value:
            tenant.status = TenantStatus.ACTIVE.value
        self._session.flush()
        return "renewed"

    def change_plan(
        self,
        tenant_id: UUID,
        *,
        plan_key: str,
        now: datetime | None = None,
    ) -> dict[str, Any]:
        moment = now or datetime.now(UTC)
        row = self._repo.get_by_tenant(tenant_id)
        if row is None:
            raise BillingError("subscription_not_found", "No subscription for tenant")
        if row.status not in ACTIVE_SUBSCRIPTION_STATUSES:
            raise BillingError(
                "subscription_inactive",
                "Activate subscription before changing plans",
            )
        new_plan = plan_key.strip().lower()
        if new_plan not in VALID_PLAN_KEYS:
            raise BillingError("invalid_plan", "Choose starter, growth, or pro")
        if new_plan == row.plan_key:
            return self._repo.serialize(row)

        old_catalog = plan_by_key(row.plan_key)
        new_catalog = plan_by_key(new_plan)
        if old_catalog is None or new_catalog is None:
            raise BillingError("invalid_plan", "Plan pricing is not available")
        old_price = int(row.monthly_price_cents or old_catalog["unit_amount"])
        new_price = int(new_catalog["unit_amount"])

        if new_price > old_price:
            # Upgrade: charge remaining-period difference.
            delta_monthly = new_price - old_price
            charge = prorate_cents(delta_monthly, now=moment)
            try:
                self._wallets.debit(
                    tenant_id,
                    amount_cents=charge,
                    idempotency_key=(
                        f"sub_upgrade:{tenant_id}:{row.plan_key}:{new_plan}:"
                        f"{moment.date().isoformat()}"
                    ),
                    reference_type="SUBSCRIPTION",
                    reference_id=str(row.id),
                    description=f"Upgrade to {new_catalog['name']} (prorated)",
                )
            except WalletError as exc:
                raise BillingError(exc.code, str(exc)) from exc
            entitlements = entitlements_for_plan(new_plan) or {}
            row.plan_key = new_plan
            row.monthly_price_cents = new_price
            row.included_minutes = int(entitlements.get("monthly_minutes") or 0)
            row.overage_rate_cents = int(
                new_catalog.get("overage_per_minute_cents") or 0
            )
            row.updated_at = moment
            self._session.flush()
            return self._repo.serialize(row)

        # Downgrade: apply next period.
        row.plan_key = new_plan
        row.monthly_price_cents = new_price
        entitlements = entitlements_for_plan(new_plan) or {}
        # Keep current included minutes until period end; snapshot new rates for renewal.
        row.overage_rate_cents = int(new_catalog.get("overage_per_minute_cents") or 0)
        # Store target included for next period via included_minutes update at renewal.
        row.included_minutes = int(entitlements.get("monthly_minutes") or 0)
        row.updated_at = moment
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor="wallet_billing",
            action="subscription_downgrade_scheduled",
            resource_ids={"plan_key": new_plan},
        )
        self._session.flush()
        return self._repo.serialize(row)
