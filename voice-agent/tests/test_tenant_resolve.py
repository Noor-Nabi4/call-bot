"""Voice-agent tenant resolve + SIP attribute helpers."""

from __future__ import annotations

import pytest

from session.state import CallState
from session.telephony import TelephonyContext
from tenant.resolve import (
    PlatformTenantResolver,
    TenantResolveError,
    sign_metadata,
    verify_signed_metadata,
)
from tenant.sip_attrs import SIP_PHONE_NUMBER, SIP_TRUNK_PHONE_NUMBER


def test_sign_and_verify_metadata() -> None:
    secret = "shared-secret"
    raw = sign_metadata({"tenant_id": "t1", "source": "playground"}, secret)
    parsed = verify_signed_metadata(raw, secret)
    assert parsed == {"tenant_id": "t1", "source": "playground"}


def test_env_fallback_non_sip() -> None:
    resolver = PlatformTenantResolver(
        platform_base_url="",
        internal_token="",
        metadata_hmac_secret="secret",
        env_tenant_id="tenant_env",
        allow_env_fallback=True,
    )
    result = resolver.resolve(
        job_metadata=None,
        called_number=None,
        livekit_inbound_trunk_id=None,
        is_sip=False,
    )
    assert result.tenant_id == "tenant_env"
    assert result.source == "env_fallback"


def test_sip_without_platform_fails_closed() -> None:
    resolver = PlatformTenantResolver(
        platform_base_url="",
        internal_token="",
        metadata_hmac_secret="secret",
        env_tenant_id="tenant_env",
        allow_env_fallback=True,
    )
    with pytest.raises(TenantResolveError):
        resolver.resolve(
            job_metadata=None,
            called_number="+15551234567",
            livekit_inbound_trunk_id=None,
            is_sip=True,
        )


def test_callstate_captures_telephony() -> None:
    state = CallState(call_id="c1", room_name="room-1")
    state.apply_telephony(
        TelephonyContext(
            caller_number="+15550001111",
            called_number="+15551234567",
            telephony_provider="twilio",
            tenant_id="tenant-1",
            provider_call_id="CA123",
            sip_participant_identity="sip_+15550001111",
            room_name="room-1",
            inbound_trunk_id="ST_1",
            dispatch_rule_id="SDR_1",
        )
    )
    assert state.tenant_id == "tenant-1"
    assert state.important_details["caller_number"] == "+15550001111"
    assert state.important_details["called_number"] == "+15551234567"
    assert SIP_PHONE_NUMBER.startswith("sip.")
    assert SIP_TRUNK_PHONE_NUMBER.startswith("sip.")
