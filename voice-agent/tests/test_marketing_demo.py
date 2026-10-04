"""Tests for public marketing demo mode (tenant-less)."""

from __future__ import annotations

from tenant.marketing import (
    MARKETING_SOURCE,
    MARKETING_TENANT_ID,
    is_marketing_demo_metadata,
    marketing_demo_profile,
    marketing_demo_resolution,
)
from tenant.resolve import sign_metadata


def test_marketing_demo_profile_has_no_tools() -> None:
    profile = marketing_demo_profile()
    assert profile.tenant_id == MARKETING_TENANT_ID
    assert profile.business_name == "Call & Flow"
    assert profile.enabled_tools == ()
    assert not profile.tool_enabled("crm")
    assert profile.greeting


def test_marketing_demo_resolution_source() -> None:
    resolution = marketing_demo_resolution()
    assert resolution.source == MARKETING_SOURCE
    assert resolution.tenant_id == MARKETING_TENANT_ID


def test_is_marketing_demo_with_signed_metadata() -> None:
    secret = "test-hmac-secret"
    raw = sign_metadata({"source": "marketing"}, secret)
    assert is_marketing_demo_metadata(raw, secret=secret, is_sip=False)
    assert not is_marketing_demo_metadata(raw, secret=secret, is_sip=True)


def test_is_marketing_demo_rejects_bad_signature() -> None:
    secret = "test-hmac-secret"
    raw = sign_metadata({"source": "marketing"}, secret)
    assert not is_marketing_demo_metadata(raw, secret="other-secret", is_sip=False)


def test_is_marketing_demo_rejects_playground_source() -> None:
    secret = "test-hmac-secret"
    raw = sign_metadata(
        {"source": "playground", "tenant_id": "t1"},
        secret,
    )
    assert not is_marketing_demo_metadata(raw, secret=secret, is_sip=False)


def test_is_marketing_demo_unsigned_when_no_secret() -> None:
    raw = '{"source":"marketing"}'
    assert is_marketing_demo_metadata(raw, secret="", is_sip=False)
