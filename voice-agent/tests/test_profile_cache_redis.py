"""Unit tests for Redis-backed Agent Profile cache."""

from __future__ import annotations

import json
from typing import Any
from unittest.mock import MagicMock

import fakeredis
import pytest

from tenant.agent_profile import AgentProfile
from tenant.profile_cache import (
    profile_cache_from_env,
    reset_default_profile_cache_for_tests,
)
from tenant.profile_cache_redis import KEY_PREFIX, RedisAgentProfileCache


def _profile(**overrides: object) -> AgentProfile:
    payload: dict[str, Any] = {
        "tenant_id": "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee",
        "business_name": "Acme HVAC",
        "assistant_name": "Riley",
        "greeting": "Thanks for calling Acme HVAC.",
        "default_language": "en",
        "supported_languages": ["en"],
        "response_style": "concise",
        "service_areas": ["Austin"],
        "profile_version": 1,
    }
    payload.update(overrides)
    return AgentProfile.from_api_payload(payload)


@pytest.fixture(autouse=True)
def _reset_default_cache(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    reset_default_profile_cache_for_tests()
    yield
    reset_default_profile_cache_for_tests()


def test_agent_profile_round_trip_payload() -> None:
    original = _profile(profile_version=3, greeting="Hi there")
    restored = AgentProfile.from_api_payload(original.to_api_payload())
    assert restored == original


def test_redis_cache_put_get_invalidate() -> None:
    fake = fakeredis.FakeRedis(decode_responses=True)
    cache = RedisAgentProfileCache(
        redis_url="redis://localhost:6379/0",
        ttl_sec=60,
        client=fake,
    )
    profile = _profile()
    cache.put(profile)
    assert cache.get(profile.tenant_id) == profile
    assert cache.get(profile.tenant_id, profile_version=1) == profile
    cache.invalidate(profile.tenant_id)
    assert cache.get(profile.tenant_id) is None


def test_redis_cache_tenant_isolation() -> None:
    fake = fakeredis.FakeRedis(decode_responses=True)
    cache = RedisAgentProfileCache(
        redis_url="redis://localhost:6379/0",
        ttl_sec=60,
        client=fake,
    )
    a = _profile(tenant_id="aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee", business_name="A")
    b = _profile(tenant_id="bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee", business_name="B")
    cache.put(a)
    cache.put(b)
    assert cache.get(a.tenant_id).business_name == "A"  # type: ignore[union-attr]
    assert cache.get(b.tenant_id).business_name == "B"  # type: ignore[union-attr]
    cache.invalidate(a.tenant_id)
    assert cache.get(a.tenant_id) is None
    assert cache.get(b.tenant_id) is not None


def test_redis_cache_rejects_cross_tenant_payload() -> None:
    fake = fakeredis.FakeRedis(decode_responses=True)
    cache = RedisAgentProfileCache(
        redis_url="redis://localhost:6379/0",
        ttl_sec=60,
        client=fake,
    )
    tenant = "aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    key = f"{KEY_PREFIX}:{tenant}:latest"
    poisoned = _profile(
        tenant_id="bbbbbbbb-bbbb-cccc-dddd-eeeeeeeeeeee",
        business_name="Evil Co",
    )
    fake.set(key, json.dumps(poisoned.to_api_payload()))
    assert cache.get(tenant) is None
    assert fake.get(key) is None


def test_redis_cache_soft_fails_on_get_error() -> None:
    broken = MagicMock()
    broken.get.side_effect = ConnectionError("down")
    cache = RedisAgentProfileCache(
        redis_url="redis://localhost:6379/0",
        ttl_sec=60,
        client=broken,
    )
    assert cache.get("aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee") is None


def test_redis_cache_soft_fails_on_put_error() -> None:
    broken = MagicMock()
    pipe = MagicMock()
    pipe.set.return_value = pipe
    pipe.execute.side_effect = ConnectionError("down")
    broken.pipeline.return_value = pipe
    cache = RedisAgentProfileCache(
        redis_url="redis://localhost:6379/0",
        ttl_sec=60,
        client=broken,
    )
    cache.put(_profile())  # must not raise


def test_profile_cache_from_env_uses_redis(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("REDIS_URL", "redis://127.0.0.1:6379/0")
    monkeypatch.setenv("AGENT_PROFILE_CACHE_TTL_SEC", "30")

    created: dict[str, Any] = {}

    class _FakeRedisCache:
        def __init__(self, *, redis_url: str, ttl_sec: float) -> None:
            created["redis_url"] = redis_url
            created["ttl_sec"] = ttl_sec

        def get(self, tenant_id: str, *, profile_version: int | None = None) -> None:
            return None

        def put(self, profile: AgentProfile) -> None:
            return None

        def invalidate(self, tenant_id: str) -> None:
            return None

    monkeypatch.setattr(
        "tenant.profile_cache_redis.RedisAgentProfileCache",
        _FakeRedisCache,
    )
    cache = profile_cache_from_env()
    assert created["redis_url"] == "redis://127.0.0.1:6379/0"
    assert created["ttl_sec"] == 30.0
    assert isinstance(cache, _FakeRedisCache)


def test_profile_cache_from_env_memory_without_redis(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("REDIS_URL", raising=False)
    from tenant.profile_cache import AgentProfileCache

    cache = profile_cache_from_env()
    assert isinstance(cache, AgentProfileCache)
