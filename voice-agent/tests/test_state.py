"""Tests for per-call state."""

from __future__ import annotations

from session.state import CallState, CallStatus


def test_call_state_tracks_activity_and_interruptions() -> None:
    state = CallState(call_id="call-1", room_name="room-1")
    assert state.current_status == CallStatus.INITIALIZING

    state.mark_active("caller-1")
    assert state.current_status == CallStatus.ACTIVE
    assert state.participant_identity == "caller-1"

    state.record_user_message("  hello there  ")
    assert state.last_user_message == "hello there"

    state.record_interruption()
    state.record_interruption()
    assert state.interruption_count == 2

    state.mark_ending("user_goodbye")
    assert state.current_status == CallStatus.ENDING
    assert state.disconnect_reason == "user_goodbye"
    assert state.duration_seconds() >= 0


def test_mark_failed_sets_error_code() -> None:
    state = CallState(call_id="call-2", room_name="room-2")
    state.mark_failed("OpenAIError")
    assert state.current_status == CallStatus.FAILED
    assert state.error_code == "OpenAIError"
