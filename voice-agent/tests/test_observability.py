"""Unit tests for Phase 1 observability helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

from config import Settings
from observability.metrics import CallMetrics
from prompts.business import BusinessFacts
from session.lifecycle import CallLifecycle
from session.state import CallState


def _settings() -> Settings:
    return Settings(
        livekit_url="wss://example.livekit.cloud",
        livekit_api_key="key",
        livekit_api_secret="secret",
        openai_api_key="sk-test",
        business_name="Acme",
        business_facts=BusinessFacts(),
        openai_realtime_model="gpt-realtime",
        openai_voice="marin",
        temperature=0.8,
        language="en",
        user_away_timeout_sec=15.0,
        max_call_duration_sec=900.0,
        inactivity_check_limit=2,
        inactivity_check_interval_sec=10.0,
        max_spoken_sentences=3,
        agent_name="voice-agent",
        tenant_id="tenant_demo",
    )


def test_record_interruption_syncs_metrics() -> None:
    state = CallState(call_id="c1", room_name="r1", tenant_id="tenant_demo")
    metrics = CallMetrics(call_id="c1", room_name="r1", tenant_id="tenant_demo")
    lifecycle = CallLifecycle(
        session=MagicMock(),
        state=state,
        metrics=metrics,
        settings=_settings(),
    )

    lifecycle.record_interruption()
    lifecycle.record_interruption()

    assert state.interruption_count == 2
    assert metrics.interruption_count == 2
    fields = metrics.as_log_fields()
    assert fields["tenant_id"] == "tenant_demo"
    assert fields["interruption_count"] == 2


def test_correlation_fields_include_tenant() -> None:
    state = CallState(
        call_id="c1",
        room_name="r1",
        tenant_id="tenant_demo",
        participant_identity="caller-1",
    )
    metrics = CallMetrics(call_id="c1", room_name="r1", tenant_id="tenant_demo")
    lifecycle = CallLifecycle(
        session=MagicMock(),
        state=state,
        metrics=metrics,
        settings=_settings(),
    )

    assert lifecycle.correlation_fields() == {
        "call_id": "c1",
        "room_name": "r1",
        "tenant_id": "tenant_demo",
        "participant_identity": "caller-1",
    }
