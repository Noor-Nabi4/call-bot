"""Deterministic tests for human-like conversation behavior and turn handling.

These verify prompt policy, realtime/session configuration, interruption
metrics, and call isolation. They do not claim live PSTN voice quality.
"""

from __future__ import annotations

import inspect
from unittest.mock import MagicMock

import pytest

from agent import _build_realtime_model, _build_session
from config import Settings
from observability.metrics import CallMetrics
from prompts import build_system_instructions_from_profile
from prompts.business import BusinessFacts, call_context_section
from prompts.call_flow import render_call_flow_section
from session.events import attach_session_events
from session.lifecycle import CallLifecycle
from session.state import CallState
from tenant.agent_profile import AgentProfile, CallFacts
from tools.knowledge import build_knowledge_tools


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "livekit_url": "wss://example.livekit.cloud",
        "livekit_api_key": "key",
        "livekit_api_secret": "secret",
        "openai_api_key": "sk-test",
        "business_name": "Acme",
        "business_facts": BusinessFacts(),
        "openai_realtime_model": "gpt-realtime",
        "openai_voice": "marin",
        "temperature": 0.85,
        "language": "en",
        "user_away_timeout_sec": 15.0,
        "max_call_duration_sec": 900.0,
        "inactivity_check_limit": 2,
        "inactivity_check_interval_sec": 10.0,
        "max_spoken_sentences": 2,
        "agent_name": "voice-agent",
        "tenant_id": "tenant_a",
        "vad_eagerness": "low",
        "input_audio_noise_reduction": None,
        "min_consecutive_speech_delay_sec": 0.25,
        "min_interruption_duration_sec": 0.5,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _profile(**overrides: object) -> AgentProfile:
    payload: dict = {
        "tenant_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "business_name": "Acme HVAC",
        "default_language": "en",
        "supported_languages": ["en"],
        "response_style": "concise",
        "business_hours_summary": "Monday to Friday, 8 AM to 6 PM",
        "service_areas": ["Austin"],
        "profile_version": 1,
        "enabled_tools": {
            "crm": True,
            "scheduling": True,
            "knowledge": True,
            "handoff": True,
        },
    }
    payload.update(overrides)
    return AgentProfile.from_api_payload(payload)


def test_prompt_supports_mid_sentence_interruption() -> None:
    prompt = build_system_instructions_from_profile(_profile())
    assert "Callers may interrupt you" in prompt
    assert "Stop and listen" in prompt
    assert "Do not restart a truncated answer" in prompt


def test_prompt_supports_answer_change_mid_conversation() -> None:
    prompt = build_system_instructions_from_profile(_profile())
    assert "change their answer mid-flow" in prompt
    assert "newest answer" in prompt


def test_prompt_supports_follow_up_without_repeating_context() -> None:
    facts = CallFacts(
        caller_name="Sam",
        requested_service="AC repair",
        preferred_time="Thursday at 2 PM",
    )
    prompt = build_system_instructions_from_profile(_profile(), call_facts=facts)
    assert "Caller name: Sam" in prompt
    assert "Requested service: AC repair" in prompt
    assert "Preferred time: Thursday at 2 PM" in prompt
    assert "Do not ask them to repeat information" in prompt
    assert "follow-up questions using earlier context" in prompt.lower()


def test_prompt_handles_pauses_and_background_noise() -> None:
    prompt = build_system_instructions_from_profile(_profile())
    assert "Brief pauses, background noise" in prompt
    assert "## Unclear audio" in prompt
    assert "ask one short clarification" in prompt.lower()


def test_prompt_forbids_repetitive_acknowledgements() -> None:
    prompt = build_system_instructions_from_profile(_profile()).lower()
    assert "never the same phrase on every turn" in prompt
    assert "fake laughter" in prompt
    assert "random filler" in prompt


def test_prompt_requires_knowledge_grounding_no_fabrication() -> None:
    prompt = build_system_instructions_from_profile(
        _profile(enabled_tools={"knowledge": True})
    )
    assert "search_knowledge" in prompt
    assert "Never invent an answer" in prompt or "Never invent" in prompt
    assert "unavailable" in prompt.lower()


def test_prompt_preserves_transfer_and_appointment_workflows() -> None:
    prompt = build_system_instructions_from_profile(_profile())
    assert "Scheduling:" in prompt
    assert "caller_confirmed=true" in prompt
    assert "Handoff:" in prompt
    assert "request_human_handoff" in prompt
    assert "explicit confirmation" in prompt.lower()


def test_call_flow_is_guided_not_scripted() -> None:
    section = render_call_flow_section(
        {
            "steps": [
                {
                    "id": "1",
                    "type": "greeting",
                    "label": "Welcome",
                    "instruction": "Say hello",
                    "enabled": True,
                }
            ]
        }
    )
    assert "GUIDED CALL FLOW" in section
    assert "not a rigid script" in section
    assert "Answer the caller's current question first" in section or (
        "answer the caller's current question first" in section.lower()
    )


def test_call_context_avoids_reasking_known_facts() -> None:
    section = call_context_section(
        CallFacts(caller_name="Alex", caller_phone="+15551234567")
    )
    assert "Treat facts already known" in section
    assert "Caller name: Alex" in section
    assert "Caller phone: +15551234567" in section


def test_realtime_model_cancels_on_interruption() -> None:
    model = _build_realtime_model(_settings())
    turn = model._opts.turn_detection
    assert turn is not None
    assert turn.type == "semantic_vad"
    assert turn.eagerness == "low"
    assert turn.interrupt_response is True
    assert turn.create_response is True


def test_realtime_model_applies_optional_noise_reduction() -> None:
    model = _build_realtime_model(_settings(input_audio_noise_reduction="near_field"))
    noise = model._opts.input_audio_noise_reduction
    assert noise is not None
    assert getattr(noise, "type", noise) == "near_field"


@pytest.mark.asyncio
async def test_session_enables_interruptions_and_speech_gap() -> None:
    session = _build_session(_settings())
    assert session.options.min_consecutive_speech_delay == 0.25
    # Turn handling stores interruption options for barge-in + false recovery.
    turn_handling = session.options.turn_handling
    interruption = turn_handling["interruption"]
    assert interruption["enabled"] is True
    assert interruption["min_duration"] == 0.5
    assert interruption["resume_false_interruption"] is True
    assert turn_handling["turn_detection"] == "realtime_llm"


def test_interruption_metrics_and_false_interruption_tracking() -> None:
    state = CallState(call_id="c1", room_name="r1", tenant_id="tenant_a")
    metrics = CallMetrics(call_id="c1", room_name="r1", tenant_id="tenant_a")
    lifecycle = CallLifecycle(
        session=MagicMock(),
        state=state,
        metrics=metrics,
        settings=_settings(),
    )
    lifecycle.record_interruption()
    lifecycle.record_false_interruption()
    lifecycle.record_failed_turn(provider_error=True)

    fields = metrics.as_log_fields()
    assert fields["interruption_count"] == 1
    assert fields["false_interruption_count"] == 1
    assert fields["failed_turn_count"] == 1
    assert fields["provider_error_count"] == 1


def test_session_error_increments_failed_turn_metrics() -> None:
    state = CallState(call_id="c1", room_name="r1", tenant_id="tenant_a")
    metrics = CallMetrics(call_id="c1", room_name="r1", tenant_id="tenant_a")
    lifecycle = CallLifecycle(
        session=MagicMock(),
        state=state,
        metrics=metrics,
        settings=_settings(),
    )
    session = MagicMock()
    handlers: dict[str, object] = {}

    def _on(event_name: str):
        def decorator(fn):
            handlers[event_name] = fn
            return fn

        return decorator

    session.on = _on
    attach_session_events(lifecycle, session)

    class _Err:
        recoverable = True

    class _Ev:
        error = _Err()

    handlers["error"](_Ev())
    assert metrics.failed_turn_count == 1
    assert metrics.provider_error_count == 1


def test_concurrent_calls_remain_isolated() -> None:
    a = CallState(call_id="call-a", room_name="room-a", tenant_id="tenant_a")
    b = CallState(call_id="call-b", room_name="room-b", tenant_id="tenant_b")
    metrics_a = CallMetrics(call_id="call-a", room_name="room-a", tenant_id="tenant_a")
    metrics_b = CallMetrics(call_id="call-b", room_name="room-b", tenant_id="tenant_b")

    a.record_interruption()
    a.record_interruption()
    metrics_a.sync_interruption_count(a.interruption_count)
    metrics_b.record_failed_turn()

    assert a.interruption_count == 2
    assert b.interruption_count == 0
    assert metrics_a.interruption_count == 2
    assert metrics_b.interruption_count == 0
    assert metrics_a.failed_turn_count == 0
    assert metrics_b.failed_turn_count == 1
    assert a.tenant_id != b.tenant_id


def test_knowledge_tools_remain_tenant_scoped() -> None:
    client = MagicMock()
    tools = build_knowledge_tools(client, metrics=None)
    assert len(tools) == 1
    # Model-facing args are query only; tenant comes from session userdata.
    params = inspect.signature(tools[0]).parameters
    assert "query" in params
    assert "tenant_id" not in params


@pytest.mark.parametrize(
    "eagerness",
    ["auto", "low", "medium", "high"],
)
def test_vad_eagerness_values_accepted(eagerness: str) -> None:
    model = _build_realtime_model(_settings(vad_eagerness=eagerness))
    assert model._opts.turn_detection.eagerness == eagerness
