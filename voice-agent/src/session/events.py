"""Wire AgentSession events into call state and metrics."""

from __future__ import annotations

from livekit.agents import (
    AgentStateChangedEvent,
    CloseEvent,
    ErrorEvent,
    UserInputTranscribedEvent,
    UserStateChangedEvent,
)
from livekit.agents.metrics import RealtimeModelMetrics

from observability.logging import get_logger, log_event
from session.lifecycle import CallLifecycle

logger = get_logger("voice-agent.events")


def attach_session_events(lifecycle: CallLifecycle, session) -> None:
    """Register session-level listeners for one call."""

    @session.on("user_state_changed")
    def on_user_state_changed(ev: UserStateChangedEvent) -> None:
        if ev.new_state == "away":
            log_event(
                logger,
                "user_away",
                call_id=lifecycle.state.call_id,
                room_name=lifecycle.state.room_name,
            )
            lifecycle.on_user_away()
            return

        if (
            ev.new_state == "speaking"
            and getattr(session, "agent_state", None) == "speaking"
        ):
            lifecycle.state.record_interruption()
            log_event(
                logger,
                "user_interruption",
                call_id=lifecycle.state.call_id,
                interruption_count=lifecycle.state.interruption_count,
            )

        lifecycle.on_user_active()

    @session.on("agent_state_changed")
    def on_agent_state_changed(ev: AgentStateChangedEvent) -> None:
        log_event(
            logger,
            "agent_state_changed",
            call_id=lifecycle.state.call_id,
            old_state=str(ev.old_state),
            new_state=str(ev.new_state),
        )

    @session.on("user_input_transcribed")
    def on_user_input_transcribed(ev: UserInputTranscribedEvent) -> None:
        if not ev.is_final:
            return
        # Store a short operational snippet only; avoid full transcript logging.
        text = (ev.transcript or "").strip()
        lifecycle.state.record_user_message(text[:200] if text else "")
        if text:
            log_event(
                logger,
                "user_turn_final",
                call_id=lifecycle.state.call_id,
                transcript_chars=len(text),
            )

    @session.on("error")
    def on_error(ev: ErrorEvent) -> None:
        recoverable = getattr(ev.error, "recoverable", None)
        error_type = type(ev.error).__name__
        log_event(
            logger,
            "session_error",
            call_id=lifecycle.state.call_id,
            error_type=error_type,
            recoverable=recoverable,
            level=40 if recoverable is False else 30,
        )
        if recoverable is False:
            lifecycle.state.mark_failed(error_type)

    @session.on("close")
    def on_close(ev: CloseEvent) -> None:
        reason = str(getattr(ev, "reason", None) or "closed")
        lifecycle.on_session_closed(reason)


def attach_realtime_metrics(
    lifecycle: CallLifecycle,
    realtime_llm_session,
) -> None:
    """Attach RealtimeModelMetrics listener (docs: metrics_realtime recipe)."""

    def on_metrics_collected(metrics: RealtimeModelMetrics) -> None:
        # ttft is -1 when no audio tokens were generated
        if metrics.ttft is not None and metrics.ttft >= 0:
            lifecycle.record_model_latency(metrics.ttft * 1000)
        log_event(
            logger,
            "realtime_metrics",
            call_id=lifecycle.state.call_id,
            request_id=getattr(metrics, "request_id", None),
            duration_ms=round(metrics.duration * 1000, 2)
            if metrics.duration is not None
            else None,
            ttft_ms=round(metrics.ttft * 1000, 2)
            if metrics.ttft is not None and metrics.ttft >= 0
            else None,
            total_tokens=getattr(metrics, "total_tokens", None),
        )

    realtime_llm_session.on("metrics_collected", on_metrics_collected)
