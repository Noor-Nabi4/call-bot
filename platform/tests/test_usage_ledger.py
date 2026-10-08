"""Phase 32 — usage ledger, cost math, idempotency, isolation, alerts."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.billing.repos import BillingRepository
from callbot_platform.billing.usage_ledger import (
    UsageAlertService,
    UsageCostAggregationService,
    UsageLedgerService,
    UsageType,
    ingest_call_end,
    ingest_sms_message,
    ingest_tool_call,
)
from callbot_platform.billing.usage_ledger.money import (
    micros_to_usd_decimal,
    multiply_unit_cost,
    usd_to_micros,
)
from callbot_platform.billing.usage_ledger.pricing import catalog_from_settings
from callbot_platform.crm.repos.call_repo import CallRepository
from callbot_platform.db.models import Call, Tenant
from callbot_platform.db.models.sms import SmsConversation, SmsMessage
from callbot_platform.db.models.usage_ledger import UsageLedgerEntry
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant


@pytest.fixture()
def ledger_tenant(session: Session, tenant: Tenant) -> Tenant:
    ensure_system_roles_for_tenant(session, tenant.id)
    sub = BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
        plan_key="starter",
    )
    sub.status = "active"
    session.flush()
    return tenant


def test_money_integer_micros() -> None:
    assert usd_to_micros(Decimal("0.01")) == 10_000
    assert multiply_unit_cost(3, 100) == 300
    assert multiply_unit_cost(0, 100) == 0
    assert micros_to_usd_decimal(1_500_000) == Decimal("1.500000")


def test_record_voice_and_idempotent(session: Session, ledger_tenant: Tenant) -> None:
    ledger = UsageLedgerService(session)
    row, created = ledger.record(
        tenant_id=ledger_tenant.id,
        usage_type=UsageType.VOICE_MINUTES,
        quantity=5,
        idempotency_key="voice:test-1",
        source_type="test",
        source_id="1",
    )
    assert created is True
    assert row.quantity == 5
    assert row.pricing_version
    assert row.unit_cost_micros is not None
    assert row.total_cost_micros == 5 * row.unit_cost_micros

    row2, created2 = ledger.record(
        tenant_id=ledger_tenant.id,
        usage_type=UsageType.VOICE_MINUTES,
        quantity=99,
        idempotency_key="voice:test-1",
        source_type="test",
        source_id="1",
    )
    assert created2 is False
    assert row2.id == row.id
    assert row2.quantity == 5


def test_llm_tokens_and_tool_calls(session: Session, ledger_tenant: Tenant) -> None:
    ledger = UsageLedgerService(session)
    ledger.record(
        tenant_id=ledger_tenant.id,
        usage_type=UsageType.LLM_INPUT_TOKENS,
        quantity=1000,
        idempotency_key="llm_in:1",
        source_type="test",
        source_id="1",
    )
    ledger.record(
        tenant_id=ledger_tenant.id,
        usage_type=UsageType.LLM_OUTPUT_TOKENS,
        quantity=200,
        idempotency_key="llm_out:1",
        source_type="test",
        source_id="1",
    )
    op = uuid.uuid4()
    created = ingest_tool_call(
        session,
        tenant_id=ledger_tenant.id,
        tool_name="find_customer",
        operation_id=op,
        call_id=None,
        ok=True,
        error_code=None,
    )
    assert created is True
    created2 = ingest_tool_call(
        session,
        tenant_id=ledger_tenant.id,
        tool_name="find_customer",
        operation_id=op,
        call_id=None,
        ok=True,
        error_code=None,
    )
    assert created2 is False


def test_call_end_ingests_ledger(session: Session, ledger_tenant: Tenant) -> None:
    started = datetime.now(UTC) - timedelta(seconds=90)
    call = Call(
        tenant_id=ledger_tenant.id,
        room_name=f"room-{uuid.uuid4().hex[:8]}",
        caller_number="+15551234567",
        status="active",
        started_at=started,
        metrics={
            "openai_usage": {
                "input_tokens": 120,
                "output_tokens": 40,
            }
        },
    )
    session.add(call)
    session.flush()
    CallRepository(session).end(
        ledger_tenant.id,
        call_id=call.id,
        metrics=call.metrics,
    )
    session.flush()
    types = {
        r.usage_type
        for r in session.scalars(
            select(UsageLedgerEntry).where(
                UsageLedgerEntry.tenant_id == ledger_tenant.id
            )
        ).all()
    }
    assert UsageType.VOICE_MINUTES.value in types
    assert UsageType.AI_REQUESTS.value in types
    assert UsageType.LLM_INPUT_TOKENS.value in types
    assert UsageType.LLM_OUTPUT_TOKENS.value in types

    # Idempotent re-ingest
    ingest_call_end(session, call)
    voice_rows = session.scalars(
        select(UsageLedgerEntry).where(
            UsageLedgerEntry.tenant_id == ledger_tenant.id,
            UsageLedgerEntry.usage_type == UsageType.VOICE_MINUTES.value,
        )
    ).all()
    assert len(voice_rows) == 1


def test_sms_idempotent_by_provider_ref(
    session: Session, ledger_tenant: Tenant
) -> None:
    conv = SmsConversation(
        tenant_id=ledger_tenant.id,
        phone_e164="+15550001111",
        business_phone_e164="+15550002222",
    )
    session.add(conv)
    session.flush()
    msg = SmsMessage(
        tenant_id=ledger_tenant.id,
        conversation_id=conv.id,
        direction="OUTBOUND",
        sender_phone=conv.business_phone_e164,
        recipient_phone=conv.phone_e164,
        body="hi",
        status="SENT",
        provider_message_id="SM123",
    )
    session.add(msg)
    session.flush()
    assert ingest_sms_message(session, msg) is True
    assert ingest_sms_message(session, msg) is False


def test_sms_queued_not_counted(session: Session, ledger_tenant: Tenant) -> None:
    conv = SmsConversation(
        tenant_id=ledger_tenant.id,
        phone_e164="+15550003333",
        business_phone_e164="+15550004444",
    )
    session.add(conv)
    session.flush()
    msg = SmsMessage(
        tenant_id=ledger_tenant.id,
        conversation_id=conv.id,
        direction="OUTBOUND",
        sender_phone=conv.business_phone_e164,
        recipient_phone=conv.phone_e164,
        body="hi",
        status="QUEUED",
        provider_message_id=None,
    )
    session.add(msg)
    session.flush()
    assert ingest_sms_message(session, msg) is False


def test_gross_margin_zero_revenue_is_null(
    session: Session, ledger_tenant: Tenant
) -> None:
    # Tenant without plan → revenue null
    other = Tenant(name="NoPlan", slug=f"np-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    ensure_system_roles_for_tenant(session, other.id)
    summary = UsageCostAggregationService(session).organization_summary(other.id)
    assert summary["revenue"]["subscription_cents"] is None
    assert summary["gross_margin"]["gross_margin_pct"] is None


def test_organization_summary_margin(session: Session, ledger_tenant: Tenant) -> None:
    from callbot_platform.billing.usage_ledger.categories import AccountingProvenance

    ledger = UsageLedgerService(session)
    ledger.record(
        tenant_id=ledger_tenant.id,
        usage_type=UsageType.VOICE_MINUTES,
        quantity=10,
        idempotency_key="voice:margin",
        source_type="test",
        source_id="m",
        usage_provenance=AccountingProvenance.ACTUAL_INTERNAL,
        cost_provenance=AccountingProvenance.CONFIGURED_RATE,
    )
    summary = UsageCostAggregationService(session).organization_summary(
        ledger_tenant.id
    )
    assert summary["usage"]["voice_minutes"] == 10
    assert summary["revenue"]["configured_subscription_revenue_cents"] == 9900
    assert summary["revenue"]["actual_revenue_cents"] is None
    assert summary["revenue"]["actual_revenue_provenance"] == "UNAVAILABLE"
    assert summary["revenue"]["estimated_overage_provenance"] == "ESTIMATED"
    # Estimated overage must never be folded into actual revenue.
    assert summary["revenue"]["total_cents"] is None
    assert summary["cost"]["total_cogs_usd"] is not None
    assert summary["gross_margin"]["verified"] is False
    assert summary["gross_margin"]["calculated_gross_margin_pct"] is not None
    assert summary["stripe_metering"]["wired"] is False


def test_tenant_isolation(session: Session, ledger_tenant: Tenant) -> None:
    other = Tenant(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    ensure_system_roles_for_tenant(session, other.id)
    ledger = UsageLedgerService(session)
    ledger.record(
        tenant_id=ledger_tenant.id,
        usage_type=UsageType.SMS,
        quantity=3,
        idempotency_key="sms:a",
        source_type="test",
        source_id="a",
    )
    ledger.record(
        tenant_id=other.id,
        usage_type=UsageType.SMS,
        quantity=9,
        idempotency_key="sms:b",
        source_type="test",
        source_id="b",
    )
    a = UsageCostAggregationService(session).organization_summary(ledger_tenant.id)
    b = UsageCostAggregationService(session).organization_summary(other.id)
    assert a["usage"]["sms"] == 3
    assert b["usage"]["sms"] == 9


def test_alert_dedupe(session: Session, ledger_tenant: Tenant) -> None:
    # Force high usage by recording many voice minutes via Call
    started = datetime.now(UTC) - timedelta(hours=5)
    for i in range(3):
        call = Call(
            tenant_id=ledger_tenant.id,
            room_name=f"r-{i}-{uuid.uuid4().hex[:6]}",
            caller_number="+15551230000",
            status="active",
            started_at=started,
        )
        session.add(call)
        session.flush()
        call.ended_at = started + timedelta(minutes=100)
        call.billable_seconds = 100 * 60
        call.status = "closed"
        session.flush()
        ingest_call_end(session, call)

    alerts = UsageAlertService(session)
    # Starter = 250 minutes; 300 minutes → 100%+
    fired = alerts.evaluate_voice_limits(ledger_tenant.id)
    assert any(a["threshold_pct"] == 100 for a in fired)
    fired2 = alerts.evaluate_voice_limits(ledger_tenant.id)
    assert fired2 == []


def test_historical_price_snapshot_stable(
    session: Session, ledger_tenant: Tenant
) -> None:
    catalog = catalog_from_settings()
    ledger = UsageLedgerService(session, catalog=catalog)
    row, _ = ledger.record(
        tenant_id=ledger_tenant.id,
        usage_type=UsageType.VOICE_MINUTES,
        quantity=1,
        idempotency_key="voice:snap",
        source_type="test",
        source_id="s",
    )
    snap_cost = row.total_cost_micros
    # Re-read — cost must not change
    again = session.get(UsageLedgerEntry, row.id)
    assert again is not None
    assert again.total_cost_micros == snap_cost
    assert again.meta_json.get("pricing_snapshot")


def test_infrastructure_null_when_unconfigured(
    session: Session, ledger_tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    from callbot_platform import config as config_mod

    settings = config_mod.get_settings()
    monkeypatch.setattr(settings, "cogs_livekit_fixed_monthly_usd", 0.0)
    monkeypatch.setattr(settings, "cogs_phone_rental_monthly_usd", 0.0)
    monkeypatch.setattr(settings, "cogs_sms_monthly_usd", 0.0)
    from callbot_platform.billing.usage_ledger import ingest_infrastructure_period

    assert (
        ingest_infrastructure_period(session, ledger_tenant.id, settings=settings)
        is False
    )


def test_fleet_requires_internal_not_tenant_leak(
    session: Session, ledger_tenant: Tenant
) -> None:
    fleet = UsageCostAggregationService(session).fleet_summary()
    assert "organizations" in fleet
    assert "period_start" in fleet
    assert fleet["actual_revenue_aggregated"] is False


def test_estimated_overage_not_in_actual_revenue(
    session: Session, ledger_tenant: Tenant
) -> None:
    """High usage creates estimated overage but actual revenue stays unavailable."""
    started = datetime.now(UTC) - timedelta(hours=10)
    for i in range(3):
        call = Call(
            tenant_id=ledger_tenant.id,
            room_name=f"ov-{i}-{uuid.uuid4().hex[:6]}",
            caller_number="+15551239999",
            status="active",
            started_at=started,
        )
        session.add(call)
        session.flush()
        call.ended_at = started + timedelta(minutes=100)
        call.billable_seconds = 100 * 60
        call.status = "closed"
        session.flush()
        ingest_call_end(session, call)

    summary = UsageCostAggregationService(session).organization_summary(
        ledger_tenant.id
    )
    assert (summary["limits"]["overage_minutes"] or 0) > 0
    assert (summary["revenue"]["estimated_overage_revenue_cents"] or 0) > 0
    assert summary["revenue"]["actual_revenue_cents"] is None
    assert summary["gross_margin"]["inputs"][
        "estimated_overage_excluded_from_calculated_margin"
    ]


def test_infrastructure_unavailable_not_zero(
    session: Session, ledger_tenant: Tenant, monkeypatch: pytest.MonkeyPatch
) -> None:
    from callbot_platform import config as config_mod

    settings = config_mod.get_settings()
    monkeypatch.setattr(settings, "cogs_livekit_fixed_monthly_usd", 0.0)
    monkeypatch.setattr(settings, "cogs_phone_rental_monthly_usd", 0.0)
    monkeypatch.setattr(settings, "cogs_sms_monthly_usd", 0.0)
    from callbot_platform.billing.usage_ledger import ingest_infrastructure_period

    assert (
        ingest_infrastructure_period(session, ledger_tenant.id, settings=settings)
        is False
    )
    summary = UsageCostAggregationService(session).organization_summary(
        ledger_tenant.id
    )
    assert summary["cost"]["infrastructure_usd"] is None
    assert summary["cost"]["provenance"]["infrastructure"] == "UNAVAILABLE"


def test_stripe_metering_boundary_noop() -> None:
    from callbot_platform.billing.usage_ledger.stripe_metering import (
        BillableUsageCandidate,
        MeteringWireStatus,
        StripeMeteringGateway,
    )

    gw = StripeMeteringGateway(enabled=False)
    assert gw.wired is False
    result = gw.enqueue_billable_usage(
        BillableUsageCandidate(
            tenant_id=uuid.uuid4(),
            usage_type="VOICE_MINUTES",
            quantity=10,
            unit="minutes",
            idempotency_key="voice:x",
            billing_period="2026-10",
            ledger_entry_id=None,
        )
    )
    assert result.status == MeteringWireStatus.NOT_WIRED
    assert result.stripe_event_id is None


def test_adjustment_does_not_overwrite_original(
    session: Session, ledger_tenant: Tenant
) -> None:
    from callbot_platform.billing.usage_ledger.adjustments import record_adjustment

    ledger = UsageLedgerService(session)
    original, _ = ledger.record(
        tenant_id=ledger_tenant.id,
        usage_type=UsageType.SMS,
        quantity=1,
        idempotency_key="sms:orig",
        source_type="test",
        source_id="orig",
    )
    adj, created = record_adjustment(
        session,
        tenant_id=ledger_tenant.id,
        usage_type=UsageType.SMS,
        quantity_delta=-1,
        original_idempotency_key="sms:orig",
        reason="provider_credit",
        actor="system",
        total_cost_micros_delta=-1000,
    )
    assert created is True
    assert adj.entry_kind == "adjustment"
    assert adj.billing_status == "ADJUSTED"
    kept = session.get(UsageLedgerEntry, original.id)
    assert kept is not None
    assert kept.quantity == 1
    assert kept.entry_kind == "usage"
