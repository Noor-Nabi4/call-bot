"""Composite SIP trunk service: Twilio Elastic SIP + LiveKit inbound trunks."""

from __future__ import annotations

from callbot_platform.telephony.adapters.livekit_sip import LiveKitSipService
from callbot_platform.telephony.adapters.twilio_adapter import TwilioSipTrunkService
from callbot_platform.telephony.interfaces import (
    LiveKitInboundTrunkInfo,
    TwilioTrunkInfo,
)


class CompositeSipTrunkService:
    def __init__(
        self,
        *,
        twilio: TwilioSipTrunkService,
        livekit: LiveKitSipService,
    ) -> None:
        self._twilio = twilio
        self._livekit = livekit

    def create_or_get_twilio_trunk(
        self,
        *,
        account_sid: str,
        auth_token: str,
        friendly_name: str,
        domain_name: str,
        livekit_origination_uri: str,
    ) -> TwilioTrunkInfo:
        return self._twilio.create_or_get_twilio_trunk(
            account_sid=account_sid,
            auth_token=auth_token,
            friendly_name=friendly_name,
            domain_name=domain_name,
            livekit_origination_uri=livekit_origination_uri,
        )

    def associate_number_with_twilio_trunk(
        self,
        *,
        account_sid: str,
        auth_token: str,
        trunk_sid: str,
        phone_number_sid: str,
    ) -> None:
        self._twilio.associate_number_with_twilio_trunk(
            account_sid=account_sid,
            auth_token=auth_token,
            trunk_sid=trunk_sid,
            phone_number_sid=phone_number_sid,
        )

    def create_livekit_inbound_trunk(
        self,
        *,
        name: str,
        numbers: list[str],
        metadata: str | None = None,
    ) -> LiveKitInboundTrunkInfo:
        return self._livekit.create_livekit_inbound_trunk(
            name=name, numbers=numbers, metadata=metadata
        )

    def delete_livekit_inbound_trunk(self, trunk_id: str) -> None:
        self._livekit.delete_livekit_inbound_trunk(trunk_id)
