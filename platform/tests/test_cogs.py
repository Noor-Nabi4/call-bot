"""Tests for internal voice COGS estimation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from callbot_platform.billing.cogs.calculator import (
    estimate_call_cogs,
    vendor_minutes_from_seconds,
)
from callbot_platform.billing.cogs.rates import CogsRates
from callbot_platform.billing.cogs.scenarios import (
    openai_sensitivity_scenarios,
    scale_minute_scenarios,
    ship_vs_scale_scenarios,
)
from callbot_platform.billing.cogs.service import CogsService
from callbot_platform.billing.cogs.types import (
    CHANNEL_BROWSER_WEBRTC,
    CHANNEL_PSTN_SIP,
    OPENAI_SOURCE_PER_MINUTE,
    OPENAI_SOURCE_TOKEN,
    TRANSFER_COLD,
    TRANSFER_NONE,
    TRANSFER_WARM,
    CallCogsInput,
)
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.billing.usage import seconds_to_billable_minutes
from callbot_platform.crm.repos.call_repo import CallRepository
from callbot_platform.db.models import Call, CallCogs, Tenant


def _rates(**overrides: float | int | str | None) -> CogsRates:
    base: dict[str, float | int | str | None] = {
        "openai_per_minute_usd": 0.0676,
        "openai_sensitivity_low_usd": 0.05,
        "openai_sensitivity_high_usd": 0.10,
        "openai_audio_input_per_1m_usd": 32.0,
        "openai_audio_cached_input_per_1m_usd": 0.40,
        "openai_audio_output_per_1m_usd": 64.0,
        "openai_text_input_per_1m_usd": 4.0,
        "openai_text_cached_input_per_1m_usd": 0.40,
        "openai_text_output_per_1m_usd": 16.0,
        "livekit_agent_per_minute_usd": 0.01,
        "livekit_agent_included_minutes_monthly": 0,
        "livekit_plan": "ship",
        "livekit_sip_ship_per_minute_usd": 0.004,
        "livekit_sip_scale_per_minute_usd": 0.003,
        "livekit_bvc_telephony_per_minute_usd": 0.0012,
        "livekit_bvc_per_minute_usd": 0.0,
        "twilio_us_local_origination_per_minute_usd": 0.0034,
        "twilio_termination_per_minute_usd": 0.01,
        "warm_transfer_termination_seconds": None,
        "livekit_fixed_monthly_usd": 50.0,
        "phone_rental_monthly_usd": 5.0,
        "sms_monthly_usd": 0.0,
    }
    base.update(overrides)
    return CogsRates(**base)  # type: ignore[arg-type]


def test_61_seconds_customer_minutes_vs_vendor_minutes() -> None:
    assert seconds_to_billable_minutes(61) == 2
    assert vendor_minutes_from_seconds(61) == 61 / 60.0
    estimate = estimate_call_cogs(
        CallCogsInput(
            billable_seconds=61,
            channel=CHANNEL_PSTN_SIP,
            transfer_kind=TRANSFER_NONE,
        ),
        _rates(),
    )
    assert estimate.vendor_minutes == 61 / 60.0
    assert estimate.openai_cost_source == OPENAI_SOURCE_PER_MINUTE
    expected = 0.0676 * (61 / 60.0)
    assert abs(estimate.openai_cost_usd - expected) < 1e-9


def test_61_seconds_openai_uses_fractional_minutes() -> None:
    estimate = estimate_call_cogs(
        CallCogsInput(billable_seconds=61, channel=CHANNEL_PSTN_SIP),
        _rates(),
    )
    expected = 0.0676 * (61 / 60.0)
    assert abs(estimate.openai_cost_usd - expected) < 1e-9
    assert seconds_to_billable_minutes(61) == 2


def test_pstn_includes_twilio_and_sip() -> None:
    estimate = estimate_call_cogs(
        CallCogsInput(billable_seconds=60, channel=CHANNEL_PSTN_SIP),
        _rates(),
    )
    assert estimate.twilio_origination_cost_usd == 0.0034
    assert estimate.livekit_sip_cost_usd == 0.004
    assert estimate.livekit_bvc_cost_usd == 0.0012
    assert estimate.livekit_agent_cost_usd == 0.01
    assert estimate.twilio_termination_cost_usd == 0.0


def test_browser_excludes_twilio_and_sip() -> None:
    estimate = estimate_call_cogs(
        CallCogsInput(billable_seconds=60, channel=CHANNEL_BROWSER_WEBRTC),
        _rates(livekit_bvc_per_minute_usd=0.0005),
    )
    assert estimate.twilio_origination_cost_usd == 0.0
    assert estimate.livekit_sip_cost_usd == 0.0
    assert estimate.twilio_termination_cost_usd == 0.0
    assert estimate.livekit_bvc_cost_usd == 0.0005
    assert estimate.livekit_agent_cost_usd == 0.01
    assert estimate.openai_cost_usd == 0.0676


def test_warm_transfer_adds_termination() -> None:
    estimate = estimate_call_cogs(
        CallCogsInput(
            billable_seconds=60,
            channel=CHANNEL_PSTN_SIP,
            transfer_kind=TRANSFER_WARM,
        ),
        _rates(),
    )
    assert estimate.twilio_termination_cost_usd == 0.01
    # Inbound SIP + warm outbound SIP
    assert abs(estimate.livekit_sip_cost_usd - 0.008) < 1e-9
    assert any("warm_transfer" in n for n in estimate.notes)


def test_cold_transfer_no_termination() -> None:
    estimate = estimate_call_cogs(
        CallCogsInput(
            billable_seconds=60,
            channel=CHANNEL_PSTN_SIP,
            transfer_kind=TRANSFER_COLD,
        ),
        _rates(),
    )
    assert estimate.twilio_termination_cost_usd == 0.0
    assert estimate.livekit_sip_cost_usd == 0.004
    assert any("cold_transfer" in n for n in estimate.notes)


def test_included_minutes_still_have_cogs() -> None:
    # Included plan minutes are a customer-billing concept; COGS still applies.
    estimate = estimate_call_cogs(
        CallCogsInput(billable_seconds=60, channel=CHANNEL_PSTN_SIP),
        _rates(),
    )
    assert estimate.total_estimated_cogs_usd > 0


def test_openai_token_usage_preferred() -> None:
    usage = {
        "provider": "openai",
        "model": "gpt-realtime",
        "input_audio_tokens": 1_000_000,
        "input_text_tokens": 0,
        "input_cached_audio_tokens": 0,
        "output_audio_tokens": 500_000,
        "output_text_tokens": 0,
    }
    estimate = estimate_call_cogs(
        CallCogsInput(
            billable_seconds=60,
            channel=CHANNEL_BROWSER_WEBRTC,
            openai_usage=usage,
        ),
        _rates(),
    )
    assert estimate.openai_cost_source == OPENAI_SOURCE_TOKEN
    # 1M audio in @ $32 + 0.5M audio out @ $64 = 32 + 32 = 64
    assert abs(estimate.openai_cost_usd - 64.0) < 1e-9


def test_openai_cached_tokens() -> None:
    usage = {
        "input_audio_tokens": 1_000_000,
        "input_cached_audio_tokens": 250_000,
        "output_audio_tokens": 0,
        "output_text_tokens": 0,
    }
    estimate = estimate_call_cogs(
        CallCogsInput(
            billable_seconds=60,
            channel=CHANNEL_BROWSER_WEBRTC,
            openai_usage=usage,
        ),
        _rates(),
    )
    # 750k uncached @ 32 + 250k cached @ 0.40
    expected = (0.75 * 32.0) + (0.25 * 0.40)
    assert abs(estimate.openai_cost_usd - expected) < 1e-9


def test_openai_sensitivity_rates() -> None:
    report = openai_sensitivity_scenarios(_rates())
    low = report["scenarios"]["low"][0]["variable"]["openai_usd"]
    base = report["scenarios"]["base"][0]["variable"]["openai_usd"]
    high = report["scenarios"]["high"][0]["variable"]["openai_usd"]
    assert abs(low - 0.05 * 1000) < 1e-6
    assert abs(base - 0.0676 * 1000) < 1e-6
    assert abs(high - 0.10 * 1000) < 1e-6


def test_ship_vs_scale() -> None:
    report = ship_vs_scale_scenarios(_rates())
    ship_sip = report["ship"][0]["variable"]["livekit_sip_usd"]
    scale_sip = report["scale"][0]["variable"]["livekit_sip_usd"]
    assert abs(ship_sip - 0.004 * 1000) < 1e-9
    assert abs(scale_sip - 0.003 * 1000) < 1e-9
    assert ship_sip > scale_sip


def test_scale_minute_scenarios() -> None:
    rows = scale_minute_scenarios(_rates())
    assert [r["minutes"] for r in rows] == [1000, 10000, 100000]
    for row in rows:
        assert row["variable"]["total_variable_usd"] > 0
        assert "fixed_monthly" in row


def test_zero_duration() -> None:
    estimate = estimate_call_cogs(
        CallCogsInput(billable_seconds=0, channel=CHANNEL_PSTN_SIP),
        _rates(),
    )
    assert estimate.total_estimated_cogs_usd == 0.0
    assert estimate.openai_cost_usd == 0.0


def test_negative_duration_treated_as_zero() -> None:
    estimate = estimate_call_cogs(
        CallCogsInput(billable_seconds=-5, channel=CHANNEL_PSTN_SIP),
        _rates(),
    )
    assert estimate.billable_seconds == 0
    assert estimate.total_estimated_cogs_usd == 0.0


def test_call_end_persists_cogs(session: Session, tenant: Tenant) -> None:
    started = CallRepository(session).start(
        tenant.id,
        room_name="cogs-call",
        telephony_provider="twilio",
        caller_number="+15550001111",
    )
    call_id = uuid.UUID(started["id"])
    row = session.get(Call, call_id)
    assert row is not None
    row.started_at = datetime.now(UTC) - timedelta(seconds=60)
    session.flush()

    CallRepository(session).end(
        tenant.id,
        call_id=call_id,
        status="closed",
        metrics={
            "call_channel": CHANNEL_PSTN_SIP,
            "transfer_kind": TRANSFER_NONE,
        },
    )
    cogs = session.get(CallCogs, call_id)
    assert cogs is not None
    assert cogs.channel == CHANNEL_PSTN_SIP
    assert cogs.total_estimated_cogs_micros > 0
    assert cogs.twilio_origination_cost_micros > 0
    assert cogs.openai_cost_source == OPENAI_SOURCE_PER_MINUTE


def test_browser_call_persists_without_twilio(session: Session, tenant: Tenant) -> None:
    started = CallRepository(session).start(
        tenant.id,
        room_name="browser-call",
        telephony_provider=None,
    )
    call_id = uuid.UUID(started["id"])
    row = session.get(Call, call_id)
    assert row is not None
    row.started_at = datetime.now(UTC) - timedelta(seconds=60)
    session.flush()

    CallRepository(session).end(
        tenant.id,
        call_id=call_id,
        status="closed",
        metrics={"call_channel": CHANNEL_BROWSER_WEBRTC},
    )
    cogs = session.get(CallCogs, call_id)
    assert cogs is not None
    assert cogs.twilio_origination_cost_micros == 0
    assert cogs.livekit_sip_cost_micros == 0
    assert cogs.total_estimated_cogs_micros > 0


def test_tenant_summary_included_and_overage(session: Session, tenant: Tenant) -> None:
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
        plan_key="starter",
    )
    repo = CallRepository(session)
    # 250 included minutes on starter; create ~2 minutes of usage.
    for i, seconds in enumerate((60, 60)):
        started = repo.start(
            tenant.id,
            room_name=f"summary-{i}",
            telephony_provider="twilio",
            caller_number="+15550003333",
        )
        call_id = uuid.UUID(started["id"])
        row = session.get(Call, call_id)
        assert row is not None
        row.started_at = datetime.now(UTC) - timedelta(seconds=seconds)
        session.flush()
        repo.end(
            tenant.id,
            call_id=call_id,
            status="closed",
            metrics={"call_channel": CHANNEL_PSTN_SIP},
        )

    summary = CogsService(session, rates=_rates()).tenant_summary(tenant.id)
    assert summary["call_count"] == 2
    assert summary["included_minutes"] == 250
    assert summary["overage_minutes"] == 0
    assert summary["variable_cogs"]["total_usd"] > 0
    assert summary["gross_revenue"]["subscription_cents"] == 9900
    assert summary["estimated"] is True


def test_overage_minutes_in_summary(session: Session, tenant: Tenant) -> None:
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
        plan_key="starter",
    )
    # Force overage by writing large billable_seconds via direct Call + COGS path.
    started = CallRepository(session).start(
        tenant.id,
        room_name="overage",
        telephony_provider="twilio",
        caller_number="+15550004444",
    )
    call_id = uuid.UUID(started["id"])
    row = session.get(Call, call_id)
    assert row is not None
    # 251 minutes of wall clock ≈ 15060 seconds
    row.started_at = datetime.now(UTC) - timedelta(seconds=251 * 60)
    session.flush()
    CallRepository(session).end(
        tenant.id,
        call_id=call_id,
        status="closed",
        metrics={"call_channel": CHANNEL_PSTN_SIP},
    )
    summary = CogsService(session, rates=_rates()).tenant_summary(tenant.id)
    assert summary["overage_minutes"] >= 1
    assert summary["gross_revenue"]["estimated_overage_cents"] > 0
    # Included minutes still produced COGS (variable total > 0).
    assert summary["variable_cogs"]["total_usd"] > 0


def test_resolve_period_windows() -> None:
    from callbot_platform.billing.cogs.periods import resolve_cogs_period

    now = datetime(2026, 9, 20, 15, 0, tzinfo=UTC)
    start, end, kind = resolve_cogs_period(period="today", now=now)
    assert kind == "today"
    assert start == datetime(2026, 9, 20, tzinfo=UTC)
    assert end == datetime(2026, 9, 21, tzinfo=UTC)

    start, end, kind = resolve_cogs_period(period="this_month", now=now)
    assert kind == "this_month"
    assert start.month == 9 and end.month == 10


def test_list_call_cogs_and_detail(session: Session, tenant: Tenant) -> None:
    started = CallRepository(session).start(
        tenant.id,
        room_name="list-cogs",
        telephony_provider="twilio",
        caller_number="+15550005555",
    )
    call_id = uuid.UUID(started["id"])
    row = session.get(Call, call_id)
    assert row is not None
    row.started_at = datetime.now(UTC) - timedelta(seconds=90)
    session.flush()
    CallRepository(session).end(
        tenant.id,
        call_id=call_id,
        status="closed",
        metrics={"call_channel": CHANNEL_PSTN_SIP, "transfer_kind": TRANSFER_WARM},
    )

    svc = CogsService(session, rates=_rates())
    listed = svc.list_call_cogs(tenant.id, period="this_month")
    assert listed["total"] >= 1
    assert listed["calls"][0]["channel"] == CHANNEL_PSTN_SIP
    assert listed["calls"][0]["revenue_usd"] is None

    detail = svc.get_call_cogs(tenant.id, call_id)
    assert detail is not None
    assert detail["transfer_kind"] == TRANSFER_WARM
    assert "openai_usage" in detail

    summary = svc.tenant_summary(tenant.id, period="30d")
    assert summary["period_kind"] == "30d"
    assert "daily_series" in summary
    assert summary["gross_revenue"]["total_usd"] is None
