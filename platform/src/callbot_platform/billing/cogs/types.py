"""Typed inputs/outputs for internal voice COGS estimates."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal

CHANNEL_PSTN_SIP = "pstn_sip"
CHANNEL_BROWSER_WEBRTC = "browser_webrtc"
CallChannel = Literal["pstn_sip", "browser_webrtc"]

TRANSFER_NONE = "none"
TRANSFER_WARM = "warm"
TRANSFER_COLD = "cold"
TransferKind = Literal["none", "warm", "cold"]

OPENAI_SOURCE_TOKEN = "token"
OPENAI_SOURCE_PER_MINUTE = "per_minute_estimate"
OpenAICostSource = Literal["token", "per_minute_estimate"]

_MICROS_PER_USD = 1_000_000


def _usd_to_micros(usd: float) -> int:
    if usd <= 0:
        return 0
    return round(usd * _MICROS_PER_USD)


@dataclass(frozen=True)
class CallCogsInput:
    billable_seconds: int
    channel: CallChannel
    transfer_kind: TransferKind = TRANSFER_NONE
    openai_usage: dict[str, Any] | None = None


@dataclass(frozen=True)
class CallCogsEstimate:
    billable_seconds: int
    vendor_minutes: float
    channel: CallChannel
    transfer_kind: TransferKind
    openai_cost_usd: float
    livekit_agent_cost_usd: float
    livekit_sip_cost_usd: float
    livekit_bvc_cost_usd: float
    twilio_origination_cost_usd: float
    twilio_termination_cost_usd: float
    total_estimated_cogs_usd: float
    openai_cost_source: OpenAICostSource
    openai_usage: dict[str, Any] | None
    rate_snapshot: dict[str, Any]
    notes: tuple[str, ...] = field(default_factory=tuple)

    @property
    def openai_cost_micros(self) -> int:
        return _usd_to_micros(self.openai_cost_usd)

    @property
    def livekit_agent_cost_micros(self) -> int:
        return _usd_to_micros(self.livekit_agent_cost_usd)

    @property
    def livekit_sip_cost_micros(self) -> int:
        return _usd_to_micros(self.livekit_sip_cost_usd)

    @property
    def livekit_bvc_cost_micros(self) -> int:
        return _usd_to_micros(self.livekit_bvc_cost_usd)

    @property
    def twilio_origination_cost_micros(self) -> int:
        return _usd_to_micros(self.twilio_origination_cost_usd)

    @property
    def twilio_termination_cost_micros(self) -> int:
        return _usd_to_micros(self.twilio_termination_cost_usd)

    @property
    def total_estimated_cogs_micros(self) -> int:
        return _usd_to_micros(self.total_estimated_cogs_usd)

    def as_dict(self) -> dict[str, Any]:
        return {
            "billable_seconds": self.billable_seconds,
            "vendor_minutes": self.vendor_minutes,
            "channel": self.channel,
            "transfer_kind": self.transfer_kind,
            "openai_cost_usd": self.openai_cost_usd,
            "livekit_agent_cost_usd": self.livekit_agent_cost_usd,
            "livekit_sip_cost_usd": self.livekit_sip_cost_usd,
            "livekit_bvc_cost_usd": self.livekit_bvc_cost_usd,
            "twilio_origination_cost_usd": self.twilio_origination_cost_usd,
            "twilio_termination_cost_usd": self.twilio_termination_cost_usd,
            "total_estimated_cogs_usd": self.total_estimated_cogs_usd,
            "openai_cost_source": self.openai_cost_source,
            "openai_usage": self.openai_usage,
            "rate_snapshot": self.rate_snapshot,
            "notes": list(self.notes),
        }
