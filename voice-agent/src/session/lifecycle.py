"""Call lifecycle orchestration around AgentSession."""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from datetime import UTC, datetime

from livekit.agents import AgentSession

from config import Settings
from observability.logging import get_logger, log_event
from observability.metrics import CallMetrics
from session.state import CallState, CallStatus

logger = get_logger("voice-agent.lifecycle")


class CallLifecycle:
    """Owns timers and graceful shutdown for one call."""

    def __init__(
        self,
        *,
        session: AgentSession,
        state: CallState,
        metrics: CallMetrics,
        settings: Settings,
        shutdown_job: Callable[[], None] | None = None,
    ) -> None:
        self._session = session
        self._state = state
        self._metrics = metrics
        self._settings = settings
        self._shutdown_job = shutdown_job
        self._inactivity_task: asyncio.Task[None] | None = None
        self._max_duration_task: asyncio.Task[None] | None = None
        self._closing = False

    @property
    def state(self) -> CallState:
        return self._state

    @property
    def metrics(self) -> CallMetrics:
        return self._metrics

    def start_max_duration_watch(self) -> None:
        if self._max_duration_task is not None:
            return
        self._max_duration_task = asyncio.create_task(
            self._enforce_max_duration(),
            name=f"max-duration-{self._state.call_id}",
        )

    async def _enforce_max_duration(self) -> None:
        try:
            await asyncio.sleep(self._settings.max_call_duration_sec)
        except asyncio.CancelledError:
            return
        log_event(
            logger,
            "max_call_duration_reached",
            call_id=self._state.call_id,
            room_name=self._state.room_name,
            max_call_duration_sec=self._settings.max_call_duration_sec,
        )
        await self.end_call(reason="max_call_duration")

    def on_user_away(self) -> None:
        if self._closing or self._inactivity_task is not None:
            return
        self._state.current_status = CallStatus.AWAY_CHECK
        self._inactivity_task = asyncio.create_task(
            self._check_user_present(),
            name=f"away-check-{self._state.call_id}",
        )

    def on_user_active(self) -> None:
        if self._inactivity_task is not None:
            self._inactivity_task.cancel()
            self._inactivity_task = None
        if self._state.current_status == CallStatus.AWAY_CHECK:
            self._state.current_status = CallStatus.ACTIVE
        self._state.touch()

    async def _check_user_present(self) -> None:
        try:
            for _ in range(self._settings.inactivity_check_limit):
                await self._session.generate_reply(
                    instructions=(
                        "The caller has been silent. Politely check if they are "
                        "still there in one short sentence."
                    )
                )
                await asyncio.sleep(self._settings.inactivity_check_interval_sec)
            await self.end_call(reason="user_inactive")
        except asyncio.CancelledError:
            return
        except Exception:
            logger.exception(
                "inactivity_check_failed",
                extra={
                    "call_id": self._state.call_id,
                    "room_name": self._state.room_name,
                },
            )
            await self.end_call(
                reason="inactivity_check_error", error_code="inactivity"
            )

    async def end_call(
        self,
        *,
        reason: str,
        error_code: str | None = None,
        status: CallStatus | None = None,
    ) -> None:
        if self._closing:
            return
        self._closing = True
        final_status = status or (
            CallStatus.FAILED if error_code else CallStatus.ENDING
        )
        if error_code:
            self._state.mark_failed(error_code)
        else:
            self._state.mark_ending(reason)

        self._cancel_background_tasks()
        self._metrics.mark_ended(
            status=final_status.value,
            disconnect_reason=reason,
            error_code=error_code,
            interruption_count=self._state.interruption_count,
        )
        log_event(
            logger,
            "call_ending",
            **self._metrics.as_log_fields(),
        )
        try:
            self._session.shutdown()
        except Exception:
            logger.exception(
                "session_shutdown_failed",
                extra={"call_id": self._state.call_id},
            )
        if self._shutdown_job is not None:
            try:
                self._shutdown_job()
            except Exception:
                logger.exception(
                    "job_shutdown_failed",
                    extra={"call_id": self._state.call_id},
                )

    def on_session_closed(self, reason: str | None) -> None:
        self._cancel_background_tasks()
        if self._state.current_status not in {CallStatus.CLOSED, CallStatus.FAILED}:
            self._state.mark_closed(reason or self._state.disconnect_reason or "closed")
        if self._metrics.ended_at is None:
            self._metrics.mark_ended(
                status=self._state.current_status.value,
                disconnect_reason=self._state.disconnect_reason or reason,
                error_code=self._state.error_code,
                interruption_count=self._state.interruption_count,
            )
        self._metrics.participant_identity = self._state.participant_identity
        log_event(logger, "call_closed", **self._metrics.as_log_fields())

    def record_model_latency(self, latency_ms: float) -> None:
        self._metrics.model_latency_ms = latency_ms
        if self._metrics.first_response_latency_ms is None:
            started = self._state.call_started_at
            elapsed_ms = (datetime.now(UTC) - started).total_seconds() * 1000
            self._metrics.first_response_latency_ms = elapsed_ms

    def _cancel_background_tasks(self) -> None:
        for task in (self._inactivity_task, self._max_duration_task):
            if task is not None and not task.done():
                task.cancel()
        self._inactivity_task = None
        self._max_duration_task = None
