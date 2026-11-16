"""Internal USD wallet: credit/debit, subscription activation, usage overage."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from sqlalchemy.orm import Session

from callbot_platform.billing.plans import plan_by_key
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.billing.service import BillingService
from callbot_platform.billing.subscription_wallet import (
    SubscriptionWalletService,
    prorate_cents,
)
from callbot_platform.billing.usage import seconds_to_billable_minutes
from callbot_platform.billing.usage_billing import UsageBillingService
from callbot_platform.billing.wallet.constants import GRACE_PERIOD_DAYS
from callbot_platform.billing.wallet.service import WalletError, WalletService
from callbot_platform.billing.wallet.topup_service import WalletTopupService
from callbot_platform.config import Settings
from callbot_platform.db.models import Call, Tenant
from callbot_platform.db.models.wallet import WalletTopup
from callbot_platform.domain.enums import TenantStatus


@pytest.fixture()
def tenant(session: Session) -> Tenant:
    row = Tenant(name="Wallet Co", slug=f"wallet-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _settings() -> Settings:
    return Settings(
        stripe_secret_key="sk_test_x",
        stripe_webhook_secret="whsec_test",
        stripe_checkout_success_url="https://example.test/ok",
        stripe_checkout_cancel_url="https://example.test/cancel",
        stripe_portal_return_url="https://example.test/portal",
        session_secret="test-session-secret",
    )


def test_wallet_credit_debit_idempotent(session: Session, tenant: Tenant) -> None:
    svc = WalletService(session)
    credit = svc.credit(
        tenant.id,
        amount_cents=15000,
        idempotency_key="topup-1",
        reference_type="TOPUP",
        description="Test top-up",
    )
    assert credit.balance_after_cents == 15000
    again = svc.credit(
        tenant.id,
        amount_cents=15000,
        idempotency_key="topup-1",
        reference_type="TOPUP",
    )
    assert again.id == credit.id
    bal = svc.get_balance(tenant.id)
    assert bal["available_balance_cents"] == 15000

    debit = svc.debit(
        tenant.id,
        amount_cents=9900,
        idempotency_key="sub-1",
        reference_type="SUBSCRIPTION",
    )
    assert debit.balance_after_cents == 5100
    with pytest.raises(WalletError) as exc:
        svc.debit(
            tenant.id,
            amount_cents=99999,
            idempotency_key="sub-fail",
            reference_type="SUBSCRIPTION",
        )
    assert exc.value.code == "insufficient_funds"


def test_wallet_reserve_and_release(session: Session, tenant: Tenant) -> None:
    svc = WalletService(session)
    svc.credit(
        tenant.id,
        amount_cents=5000,
        idempotency_key="fund-reserve",
        reference_type="TOPUP",
    )
    hold = svc.reserve(
        tenant.id,
        amount_cents=500,
        idempotency_key="call-hold-1",
        reference_type="CALL",
    )
    assert hold.status == "OPEN"
    bal = svc.get_balance(tenant.id)
    assert bal["available_balance_cents"] == 4500
    assert bal["reserved_balance_cents"] == 500
    again = svc.reserve(
        tenant.id,
        amount_cents=500,
        idempotency_key="call-hold-1",
        reference_type="CALL",
    )
    assert again.id == hold.id
    released = svc.release_reservation(tenant.id, idempotency_key="call-hold-1")
    assert released is not None
    assert released.status == "RELEASED"
    bal2 = svc.get_balance(tenant.id)
    assert bal2["available_balance_cents"] == 5000
    assert bal2["reserved_balance_cents"] == 0


def test_subscription_activate_and_usage_overage(
    session: Session, tenant: Tenant
) -> None:
    wallets = WalletService(session)
    wallets.credit(
        tenant.id,
        amount_cents=20000,
        idempotency_key="fund",
        reference_type="TOPUP",
    )
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id=None,
        plan_key="starter",
        provisioning_status="ready",
    )
    session.flush()

    sub_svc = SubscriptionWalletService(session)
    activated = sub_svc.activate_from_wallet(tenant.id, plan_key="starter")
    assert activated["status"] == "active"
    assert activated["plan_key"] == "starter"
    bal = wallets.get_balance(tenant.id)
    # Prorated starter fee deducted from 20000.
    assert bal["available_balance_cents"] < 20000
    assert bal["available_balance_cents"] >= 20000 - 9900

    # Simulate month with included minutes already consumed.
    sub = BillingRepository(session).get_by_tenant(tenant.id)
    assert sub is not None
    sub.included_minutes = 250
    sub.included_minutes_consumed = 250
    sub.overage_rate_cents = 35
    session.flush()

    call = Call(
        tenant_id=tenant.id,
        room_name=f"room-{uuid.uuid4().hex[:8]}",
        status="completed",
        started_at=datetime.now(UTC) - timedelta(minutes=50),
        ended_at=datetime.now(UTC),
        billable_seconds=50 * 60,
    )
    session.add(call)
    session.flush()

    result = UsageBillingService(session).charge_call_overage(tenant.id, call.id)
    assert result["status"] == "CHARGED"
    assert result["overage_minutes"] == 50
    assert result["total_amount_cents"] == 50 * 35

    # Duplicate call completion must not double-charge.
    again = UsageBillingService(session).charge_call_overage(tenant.id, call.id)
    assert again["id"] == result["id"]


def test_renewal_past_due_then_suspended(session: Session, tenant: Tenant) -> None:
    wallets = WalletService(session)
    wallets.credit(
        tenant.id,
        amount_cents=20000,
        idempotency_key="fund-renew",
        reference_type="TOPUP",
    )
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id="cus_renew",
        plan_key="starter",
        provisioning_status="ready",
    )
    session.flush()
    sub_svc = SubscriptionWalletService(session)
    sub_svc.activate_from_wallet(tenant.id, plan_key="starter")
    sub = BillingRepository(session).get_by_tenant(tenant.id)
    assert sub is not None
    # Force due immediately with empty wallet.
    sub.next_billing_at = datetime.now(UTC) - timedelta(minutes=1)
    session.flush()
    # Drain wallet so renewal fails.
    bal = wallets.get_balance(tenant.id)
    if bal["available_balance_cents"] > 0:
        wallets.debit(
            tenant.id,
            amount_cents=int(bal["available_balance_cents"]),
            idempotency_key="drain",
            reference_type="ADMIN",
        )

    due_moment = datetime.now(UTC)
    first = sub_svc.renew_due(now=due_moment)
    assert first["past_due"] == 1
    session.refresh(sub)
    assert sub.status == "past_due"
    assert sub.grace_period_ends_at is not None

    # Entitled during grace if wallet has funds.
    wallets.credit(
        tenant.id,
        amount_cents=100,
        idempotency_key="grace-fund",
        reference_type="TOPUP",
    )
    assert BillingService(session, _settings()).tenant_is_entitled(tenant.id) is True

    # After grace with still-insufficient balance for full renewal → suspended.
    sub.next_billing_at = due_moment - timedelta(minutes=1)
    sub.grace_period_ends_at = due_moment - timedelta(seconds=1)
    session.flush()
    # Keep balance below monthly fee.
    second = sub_svc.renew_due(now=due_moment + timedelta(days=GRACE_PERIOD_DAYS))
    assert second["suspended"] == 1
    session.refresh(sub)
    session.refresh(tenant)
    assert sub.status == "suspended"
    assert tenant.status == TenantStatus.SUSPENDED.value
    assert BillingService(session, _settings()).tenant_is_entitled(tenant.id) is False


def test_zero_balance_blocks_entitlement(session: Session, tenant: Tenant) -> None:
    wallets = WalletService(session)
    wallets.credit(
        tenant.id,
        amount_cents=20000,
        idempotency_key="fund-ent",
        reference_type="TOPUP",
    )
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id=None,
        plan_key="starter",
        provisioning_status="ready",
    )
    session.flush()
    SubscriptionWalletService(session).activate_from_wallet(
        tenant.id, plan_key="starter"
    )
    svc = BillingService(session, _settings())
    assert svc.tenant_is_entitled(tenant.id) is True
    bal = wallets.get_balance(tenant.id)
    wallets.debit(
        tenant.id,
        amount_cents=int(bal["available_balance_cents"]),
        idempotency_key="drain-ent",
        reference_type="ADMIN",
    )
    assert svc.tenant_is_entitled(tenant.id) is False
    assert wallets.can_start_billable_call(tenant.id) is False


def test_topup_credit_and_refund_idempotent(session: Session, tenant: Tenant) -> None:
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id="cus_top",
        plan_key="starter",
        provisioning_status="ready",
    )
    session.flush()
    wallets = WalletService(session)
    wallet = wallets.ensure_wallet(tenant.id)
    topup = WalletTopup(
        tenant_id=tenant.id,
        wallet_id=wallet.id,
        amount_cents=5000,
        currency="USD",
        status="PENDING",
        stripe_checkout_session_id="cs_test_1",
        stripe_payment_intent_id="pi_test_1",
    )
    session.add(topup)
    session.flush()

    topups = WalletTopupService(session, _settings())
    session_obj: dict[str, Any] = {
        "id": "cs_test_1",
        "mode": "payment",
        "payment_status": "paid",
        "amount_total": 5000,
        "payment_intent": "pi_test_1",
        "metadata": {
            "purpose": "wallet_topup",
            "tenant_id": str(tenant.id),
            "wallet_topup_id": str(topup.id),
            "plan_key": "starter",
            "auto_activate_plan": "0",
        },
    }
    first = topups.credit_from_checkout_session(session_obj)
    assert first["ok"] is True
    assert first["duplicate"] is False
    second = topups.credit_from_checkout_session(session_obj)
    assert second["duplicate"] is True
    assert wallets.get_balance(tenant.id)["available_balance_cents"] == 5000

    refund = topups.handle_refund(
        {"payment_intent": "pi_test_1", "amount_refunded": 5000}
    )
    assert refund["ok"] is True
    assert wallets.get_balance(tenant.id)["available_balance_cents"] == 0
    again = topups.handle_refund(
        {"payment_intent": "pi_test_1", "amount_refunded": 5000}
    )
    assert again.get("duplicate") is True


def test_legacy_subscription_webhook_ignored(session: Session, tenant: Tenant) -> None:
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id="cus_legacy",
        plan_key="starter",
    )
    session.flush()
    service = BillingService(session, _settings())
    event = {
        "id": "evt_legacy_sub",
        "type": "customer.subscription.updated",
        "data": {
            "object": {
                "id": "sub_x",
                "customer": "cus_legacy",
                "status": "active",
                "metadata": {"tenant_id": str(tenant.id), "plan_key": "starter"},
            }
        },
    }
    result = service.handle_webhook_event(event)  # type: ignore[arg-type]
    assert result["ok"] is True
    sub = BillingRepository(session).get_by_tenant(tenant.id)
    assert sub is not None
    assert sub.status == "incomplete"
    assert service.tenant_is_entitled(tenant.id) is False


def test_prorate_and_minutes_helpers() -> None:
    assert seconds_to_billable_minutes(61) == 2
    assert prorate_cents(9900) > 0
    starter = plan_by_key("starter")
    assert starter is not None
    assert starter["overage_per_minute_cents"] == 35


def test_plan_upgrade_debits_delta(session: Session, tenant: Tenant) -> None:
    wallets = WalletService(session)
    wallets.credit(
        tenant.id,
        amount_cents=100000,
        idempotency_key="fund-upgrade",
        reference_type="TOPUP",
    )
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id=None,
        plan_key="starter",
        provisioning_status="ready",
    )
    session.flush()
    sub_svc = SubscriptionWalletService(session)
    sub_svc.activate_from_wallet(tenant.id, plan_key="starter")
    before = wallets.get_balance(tenant.id)["available_balance_cents"]
    upgraded = sub_svc.change_plan(tenant.id, plan_key="growth")
    assert upgraded["plan_key"] == "growth"
    after = wallets.get_balance(tenant.id)["available_balance_cents"]
    assert after < before
