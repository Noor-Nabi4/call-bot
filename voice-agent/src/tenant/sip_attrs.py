"""Extract SIP participant attributes into telephony context.

Docs: https://docs.livekit.io/reference/telephony/sip-participant/
"""

from __future__ import annotations

from livekit import rtc

from session.telephony import TelephonyContext

# LiveKit SIP attribute keys
SIP_PHONE_NUMBER = "sip.phoneNumber"
SIP_TRUNK_PHONE_NUMBER = "sip.trunkPhoneNumber"
SIP_CALL_ID = "sip.callID"
SIP_TRUNK_ID = "sip.trunkID"


def is_sip_participant(participant: rtc.RemoteParticipant) -> bool:
    return participant.kind == rtc.ParticipantKind.PARTICIPANT_KIND_SIP


def extract_sip_context(
    participant: rtc.RemoteParticipant,
    *,
    room_name: str,
    tenant_id: str | None = None,
    dispatch_rule_id: str | None = None,
) -> TelephonyContext:
    attrs = dict(participant.attributes or {})
    return TelephonyContext(
        caller_number=attrs.get(SIP_PHONE_NUMBER),
        called_number=attrs.get(SIP_TRUNK_PHONE_NUMBER),
        telephony_provider="twilio",
        tenant_id=tenant_id,
        provider_call_id=attrs.get(SIP_CALL_ID),
        sip_participant_identity=participant.identity,
        room_name=room_name,
        inbound_trunk_id=attrs.get(SIP_TRUNK_ID),
        dispatch_rule_id=dispatch_rule_id,
    )
