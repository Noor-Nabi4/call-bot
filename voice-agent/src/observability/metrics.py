"""Operational metrics for a single call."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CallMetrics:
    call_id: str
    room_name: str
    participant_identity: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    status: str = "initializing"
    disconnect_reason: str | None = None
    first_response_latency_ms: float | None = None
    model_latency_ms: float | None = None
    interruption_count: int = 0
    error_code: str | None = None

    def mark_ended(
        self,
        *,
        status: str,
        disconnect_reason: str | None = None,
        error_code: str | None = None,
        interruption_count: int | None = None,
    ) -> None:
        self.ended_at = datetime.now(UTC)
        self.status = status
        if disconnect_reason is not None:
            self.disconnect_reason = disconnect_reason
        if error_code is not None:
            self.error_code = error_code
        if interruption_count is not None:
            self.interruption_count = interruption_count

    @property
    def duration_sec(self) -> float | None:
        if self.ended_at is None:
            return None
        return max(0.0, (self.ended_at - self.started_at).total_seconds())

    def as_log_fields(self) -> dict[str, object]:
        return {
            "call_id": self.call_id,
            "room_name": self.room_name,
            "participant_identity": self.participant_identity,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_sec": self.duration_sec,
            "status": self.status,
            "disconnect_reason": self.disconnect_reason,
            "first_response_latency_ms": self.first_response_latency_ms,
            "model_latency_ms": self.model_latency_ms,
            "interruption_count": self.interruption_count,
            "error_code": self.error_code,
        }
