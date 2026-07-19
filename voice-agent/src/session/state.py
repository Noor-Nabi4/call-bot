"""Per-call operational state (not long-term memory)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import Enum
from typing import Any


class CallStatus(str, Enum):
    INITIALIZING = "initializing"
    ACTIVE = "active"
    AWAY_CHECK = "away_check"
    ENDING = "ending"
    CLOSED = "closed"
    FAILED = "failed"


@dataclass
class CallState:
    """Typed operational state for the active call only."""

    call_id: str
    room_name: str
    # Optional until Phase 2-3 tenant resolution. Prefer env TENANT_ID in Phase 0/1.
    tenant_id: str | None = None
    participant_identity: str | None = None
    call_started_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    current_status: CallStatus = CallStatus.INITIALIZING
    important_details: dict[str, Any] = field(default_factory=dict)
    last_user_message: str | None = None
    last_activity_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    greeting_sent: bool = False
    interruption_count: int = 0
    error_code: str | None = None
    disconnect_reason: str | None = None

    def mark_active(self, participant_identity: str | None = None) -> None:
        if participant_identity:
            self.participant_identity = participant_identity
        self.current_status = CallStatus.ACTIVE
        self.touch()

    def touch(self) -> None:
        self.last_activity_at = datetime.now(UTC)

    def record_user_message(self, text: str) -> None:
        cleaned = text.strip()
        if not cleaned:
            return
        self.last_user_message = cleaned
        self.touch()

    def record_interruption(self) -> None:
        self.interruption_count += 1
        self.touch()

    def mark_ending(self, reason: str) -> None:
        self.current_status = CallStatus.ENDING
        self.disconnect_reason = reason
        self.touch()

    def mark_closed(self, reason: str | None = None) -> None:
        self.current_status = CallStatus.CLOSED
        if reason:
            self.disconnect_reason = reason
        self.touch()

    def mark_failed(self, error_code: str) -> None:
        self.current_status = CallStatus.FAILED
        self.error_code = error_code
        self.touch()

    def duration_seconds(self, ended_at: datetime | None = None) -> float:
        end = ended_at or datetime.now(UTC)
        return max(0.0, (end - self.call_started_at).total_seconds())
