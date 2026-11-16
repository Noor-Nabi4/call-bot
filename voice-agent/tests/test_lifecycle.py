"""Tests for call lifecycle helpers."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from config import Settings
from observability.metrics import CallMetrics
from session.lifecycle import CallLifecycle
from session.state import CallState, CallStatus


def _settings() -> Settings:
    from prompts.business import BusinessFacts

    return Settings(
        livekit_url="wss://example.livekit.cloud",
        livekit_api_key="key",
        livekit_api_secret="secret",
        openai_api_key="sk-test",
        business_name="Acme",
        business_facts=BusinessFacts(),
        openai_realtime_model="gpt-realtime",
        openai_voice="marin",
        temperature=0.85,
        language="en",
        user_away_timeout_sec=15.0,
        max_call_duration_sec=900.0,
        inactivity_check_limit=2,
        inactivity_check_interval_sec=10.0,
        max_spoken_sentences=3,
        agent_name="voice-agent",
        tenant_id="tenant_demo",
        vad_eagerness="low",
        input_audio_noise_reduction=None,
        min_consecutive_speech_delay_sec=0.25,
        min_interruption_duration_sec=0.5,
    )


@pytest.mark.asyncio
async def test_end_call_shuts_down_session() -> None:
    session = MagicMock()
    shutdown_job = MagicMock()
    state = CallState(call_id="c1", room_name="r1")
    metrics = CallMetrics(call_id="c1", room_name="r1")
    lifecycle = CallLifecycle(
        session=session,
        state=state,
        metrics=metrics,
        settings=_settings(),
        shutdown_job=shutdown_job,
    )

    await lifecycle.end_call(reason="user_inactive")

    assert state.current_status == CallStatus.ENDING
    assert state.disconnect_reason == "user_inactive"
    assert metrics.ended_at is not None
    assert metrics.disconnect_reason == "user_inactive"
    session.shutdown.assert_called_once()
    shutdown_job.assert_called_once()


@pytest.mark.asyncio
async def test_end_call_is_idempotent() -> None:
    session = MagicMock()
    state = CallState(call_id="c1", room_name="r1")
    metrics = CallMetrics(call_id="c1", room_name="r1")
    lifecycle = CallLifecycle(
        session=session,
        state=state,
        metrics=metrics,
        settings=_settings(),
    )

    await lifecycle.end_call(reason="max_call_duration")
    await lifecycle.end_call(reason="second")

    session.shutdown.assert_called_once()


def test_on_session_closed_finalizes_metrics() -> None:
    session = MagicMock()
    state = CallState(call_id="c1", room_name="r1")
    state.mark_active("caller")
    metrics = CallMetrics(call_id="c1", room_name="r1")
    lifecycle = CallLifecycle(
        session=session,
        state=state,
        metrics=metrics,
        settings=_settings(),
    )

    lifecycle.on_session_closed("participant_disconnected")

    assert state.current_status == CallStatus.CLOSED
    assert metrics.status == CallStatus.CLOSED.value
    assert metrics.participant_identity == "caller"
