"""Tests for multi-profile agent loading, tool gating, and cache keys."""

from __future__ import annotations

from tenant.agent_profile import AgentProfile
from tenant.profile_cache import AgentProfileCache
from tenant.resolve import TenantResolution, sign_metadata, verify_signed_metadata


def test_agent_profile_parses_enabled_tools_and_id() -> None:
    profile = AgentProfile.from_api_payload(
        {
            "tenant_id": "t1",
            "business_name": "Acme",
            "agent_profile_id": "p1",
            "name": "Sales",
            "agent_type": "sales",
            "enabled_tools": {"crm": True, "scheduling": False, "knowledge": True},
            "profile_version": 3,
        }
    )
    assert profile.agent_profile_id == "p1"
    assert profile.tool_enabled("crm")
    assert not profile.tool_enabled("scheduling")
    assert profile.tool_enabled("knowledge")
    assert not profile.tool_enabled("handoff")


def test_cache_isolates_profiles_per_id() -> None:
    cache = AgentProfileCache(ttl_sec=60)
    a = AgentProfile.from_api_payload(
        {
            "tenant_id": "t1",
            "business_name": "Acme",
            "agent_profile_id": "p-a",
            "greeting": "A",
            "profile_version": 1,
        }
    )
    b = AgentProfile.from_api_payload(
        {
            "tenant_id": "t1",
            "business_name": "Acme",
            "agent_profile_id": "p-b",
            "greeting": "B",
            "profile_version": 1,
        }
    )
    cache.put(a, cache_key="t1:p-a")
    cache.put(b, cache_key="t1:p-b")
    got_a = cache.get("t1:p-a")
    got_b = cache.get("t1:p-b")
    assert got_a is not None and got_a.greeting == "A"
    assert got_b is not None and got_b.greeting == "B"
    cache.invalidate("t1:p-a")
    assert cache.get("t1:p-a") is None
    assert cache.get("t1:p-b") is not None


def test_signed_metadata_includes_agent_profile_id() -> None:
    secret = "test-secret"
    raw = sign_metadata(
        {"tenant_id": "t1", "agent_profile_id": "p9", "source": "ops_test_call"},
        secret,
    )
    body = verify_signed_metadata(raw, secret)
    assert body is not None
    assert body["agent_profile_id"] == "p9"


def test_tenant_resolution_carries_profile_id() -> None:
    res = TenantResolution(
        tenant_id="t1",
        phone_number_id="ph1",
        e164="+15551234567",
        source="did_mapping",
        agent_profile_id="prof-1",
    )
    assert res.agent_profile_id == "prof-1"
