"""Telephony / SIP attributes on the active call."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class TelephonyContext:
    caller_number: str | None = None
    called_number: str | None = None
    telephony_provider: str | None = None
    tenant_id: str | None = None
    provider_call_id: str | None = None
    sip_participant_identity: str | None = None
    room_name: str | None = None
    inbound_trunk_id: str | None = None
    dispatch_rule_id: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {
            "caller_number": self.caller_number,
            "called_number": self.called_number,
            "telephony_provider": self.telephony_provider,
            "tenant_id": self.tenant_id,
            "provider_call_id": self.provider_call_id,
            "sip_participant_identity": self.sip_participant_identity,
            "room_name": self.room_name,
            "inbound_trunk_id": self.inbound_trunk_id,
            "dispatch_rule_id": self.dispatch_rule_id,
        }
