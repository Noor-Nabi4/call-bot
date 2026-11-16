"""Telephony transfer provider abstraction (no provider SDK in domain)."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class TransferRequest:
    tenant_id: str
    call_id: str | None
    destination_e164: str
    mode: str  # warm | cold
    sip_outbound_trunk_id: str | None
    context_summary: str | None


@dataclass(frozen=True)
class TransferResult:
    status: str  # INITIATED | QUEUED | UNAVAILABLE | FAILED
    provider: str
    detail: dict[str, Any]


class TelephonyTransferProvider(ABC):
    @abstractmethod
    def transfer_call(self, request: TransferRequest) -> TransferResult:
        raise NotImplementedError


class NoOpTransferProvider(TelephonyTransferProvider):
    """Default when LiveKit/Twilio transfer is not configured in-process.

    Voice-agent executes LiveKit SIP transfer separately; platform records intent.
    """

    def transfer_call(self, request: TransferRequest) -> TransferResult:
        if not request.destination_e164:
            return TransferResult(
                status="UNAVAILABLE",
                provider="noop",
                detail={"reason": "no_destination"},
            )
        return TransferResult(
            status="INITIATED",
            provider="noop",
            detail={
                "destination": request.destination_e164,
                "mode": request.mode,
                "note": "platform_recorded_transfer_intent",
            },
        )


class RecordingTransferProvider(TelephonyTransferProvider):
    """Test adapter that records transfer calls without network I/O."""

    def __init__(self) -> None:
        self.calls: list[TransferRequest] = []

    def transfer_call(self, request: TransferRequest) -> TransferResult:
        self.calls.append(request)
        return TransferResult(
            status="INITIATED",
            provider="test",
            detail={"destination": request.destination_e164},
        )


class TwilioTransferProvider(TelephonyTransferProvider):
    """Placeholder — wire Twilio REST transfer outside domain services."""

    def transfer_call(self, request: TransferRequest) -> TransferResult:
        return TransferResult(
            status="UNAVAILABLE",
            provider="twilio",
            detail={"reason": "not_implemented"},
        )


class LiveKitTransferProvider(TelephonyTransferProvider):
    """Placeholder — LiveKit SIP transfer remains in the voice-agent worker."""

    def transfer_call(self, request: TransferRequest) -> TransferResult:
        return TransferResult(
            status="UNAVAILABLE",
            provider="livekit",
            detail={"reason": "delegated_to_voice_agent"},
        )
