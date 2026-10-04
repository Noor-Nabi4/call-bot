"""Tests for OpenAI usage snapshot + COGS-related CallMetrics fields."""

from __future__ import annotations

from types import SimpleNamespace

from observability.metrics import (
    CHANNEL_BROWSER_WEBRTC,
    CHANNEL_PSTN_SIP,
    TRANSFER_COLD,
    TRANSFER_WARM,
    CallMetrics,
)
from observability.openai_usage import (
    accumulate_realtime_turn,
    snapshot_from_session_usage,
    snapshot_from_turn_accumulator,
)


def test_call_channel_and_transfer_in_log_fields() -> None:
    metrics = CallMetrics(call_id="c1", room_name="r1")
    metrics.set_call_channel(is_sip=True)
    metrics.record_transfer("warm")
    fields = metrics.as_log_fields()
    assert fields["call_channel"] == CHANNEL_PSTN_SIP
    assert fields["transfer_kind"] == TRANSFER_WARM
    assert fields["handoff_requested"] is True

    metrics.set_call_channel(is_sip=False)
    metrics.record_transfer("cold")
    fields = metrics.as_log_fields()
    assert fields["call_channel"] == CHANNEL_BROWSER_WEBRTC
    assert fields["transfer_kind"] == TRANSFER_COLD


def test_snapshot_from_session_usage() -> None:
    entry = SimpleNamespace(
        provider="openai",
        model="gpt-realtime",
        input_tokens=100,
        input_cached_tokens=10,
        input_cached_audio_tokens=8,
        input_cached_text_tokens=2,
        input_cached_image_tokens=0,
        input_audio_tokens=80,
        input_text_tokens=20,
        input_image_tokens=0,
        output_tokens=50,
        output_audio_tokens=40,
        output_text_tokens=10,
        session_duration=12.5,
    )
    session = SimpleNamespace(usage=SimpleNamespace(model_usage=[entry]))
    snap = snapshot_from_session_usage(session)
    assert snap is not None
    assert snap["input_tokens"] == 100
    assert snap["output_audio_tokens"] == 40
    assert snap["input_cached_audio_tokens"] == 8


def test_turn_accumulator_fallback() -> None:
    acc: dict[str, int] = {}
    turn = SimpleNamespace(
        input_tokens=10,
        output_tokens=5,
        total_tokens=15,
        input_token_details=SimpleNamespace(
            audio_tokens=8, text_tokens=2, cached_tokens=1
        ),
        output_token_details=SimpleNamespace(audio_tokens=4, text_tokens=1),
    )
    accumulate_realtime_turn(acc, turn)
    accumulate_realtime_turn(acc, turn)
    snap = snapshot_from_turn_accumulator(acc)
    assert snap is not None
    assert snap["input_tokens"] == 20
    assert snap["output_tokens"] == 10
    assert snap["input_cached_tokens"] == 2
