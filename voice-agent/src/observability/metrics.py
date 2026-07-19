"""Operational metrics for a single call."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime


@dataclass
class CallMetrics:
    call_id: str
    room_name: str
    tenant_id: str | None = None
    participant_identity: str | None = None
    started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    ended_at: datetime | None = None
    status: str = "initializing"
    disconnect_reason: str | None = None
    first_response_latency_ms: float | None = None
    model_latency_ms: float | None = None
    response_latency_ms: float | None = None
    interruption_count: int = 0
    error_code: str | None = None
    agent_profile_version: int | None = None
    requested_language: str | None = None
    tool_name: str | None = None
    tool_result_status: str | None = None
    knowledge_lookup_used: bool = False
    handoff_requested: bool = False

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

    def sync_interruption_count(self, count: int) -> None:
        self.interruption_count = count

    def record_tool(
        self,
        tool_name: str,
        *,
        ok: bool,
        knowledge: bool = False,
        handoff: bool = False,
    ) -> None:
        self.tool_name = tool_name
        self.tool_result_status = "ok" if ok else "error"
        if knowledge and ok:
            self.knowledge_lookup_used = True
        if handoff:
            self.handoff_requested = True

    @property
    def duration_sec(self) -> float | None:
        if self.ended_at is None:
            return None
        return max(0.0, (self.ended_at - self.started_at).total_seconds())

    def as_log_fields(self) -> dict[str, object]:
        return {
            "call_id": self.call_id,
            "room_name": self.room_name,
            "tenant_id": self.tenant_id,
            "participant_identity": self.participant_identity,
            "started_at": self.started_at.isoformat(),
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "duration_sec": self.duration_sec,
            "status": self.status,
            "disconnect_reason": self.disconnect_reason,
            "first_response_latency_ms": self.first_response_latency_ms,
            "model_latency_ms": self.model_latency_ms,
            "response_latency_ms": self.response_latency_ms,
            "interruption_count": self.interruption_count,
            "error_code": self.error_code,
            "agent_profile_version": self.agent_profile_version,
            "requested_language": self.requested_language,
            "tool_name": self.tool_name,
            "tool_result_status": self.tool_result_status,
            "knowledge_lookup_used": self.knowledge_lookup_used,
            "handoff_requested": self.handoff_requested,
        }
