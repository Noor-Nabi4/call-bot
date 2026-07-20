"""Agent Profile caches: in-process and Redis-backed."""

from __future__ import annotations

import os
import threading
import time
from dataclasses import dataclass
from typing import Protocol

from tenant.agent_profile import AgentProfile


class AgentProfileCacheProto(Protocol):
    def get(
        self, tenant_id: str, *, profile_version: int | None = None
    ) -> AgentProfile | None: ...

    def put(self, profile: AgentProfile, *, cache_key: str | None = None) -> None: ...

    def invalidate(self, tenant_id: str) -> None: ...


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    profile: AgentProfile
    expires_at: float


def _scope_key(tenant_id: str, agent_profile_id: str | None = None) -> str:
    """Cache scope: tenant alone (default) or tenant:profile_id."""
    if agent_profile_id:
        return f"{tenant_id}:{agent_profile_id}"
    return tenant_id


class AgentProfileCache:
    """Bounded TTL cache keyed by tenant (+ optional profile id) + version.

    Never shares entries across tenants or profiles. Expired entries are not returned.
    """

    def __init__(self, *, ttl_sec: float = 60.0, max_entries: int = 256) -> None:
        if ttl_sec <= 0:
            raise ValueError("ttl_sec must be positive")
        if max_entries < 1:
            raise ValueError("max_entries must be >= 1")
        self._ttl_sec = ttl_sec
        self._max_entries = max_entries
        self._lock = threading.Lock()
        self._entries: dict[str, _CacheEntry] = {}

    @staticmethod
    def _key(
        scope: str,
        profile_version: int | None = None,
    ) -> str:
        if profile_version is None:
            return f"{scope}:latest"
        return f"{scope}:v{profile_version}"

    def get(
        self, tenant_id: str, *, profile_version: int | None = None
    ) -> AgentProfile | None:
        # tenant_id may be a composite cache key (tenant:profile_id).
        scope = tenant_id
        tenant_only = tenant_id.split(":", 1)[0]
        key = self._key(scope, profile_version)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                del self._entries[key]
                return None
            if entry.profile.tenant_id != tenant_only:
                del self._entries[key]
                return None
            if (
                profile_version is not None
                and entry.profile.profile_version != profile_version
            ):
                del self._entries[key]
                return None
            return entry.profile

    def put(self, profile: AgentProfile, *, cache_key: str | None = None) -> None:
        now = time.monotonic()
        expires_at = now + self._ttl_sec
        scope = cache_key or _scope_key(profile.tenant_id, profile.agent_profile_id)
        versioned = self._key(scope, profile.profile_version)
        latest = self._key(scope, None)
        entry = _CacheEntry(profile=profile, expires_at=expires_at)
        with self._lock:
            self._entries[versioned] = entry
            self._entries[latest] = entry
            self._evict_expired_locked(now)
            while len(self._entries) > self._max_entries:
                oldest = next(iter(self._entries))
                del self._entries[oldest]

    def invalidate(self, tenant_id: str) -> None:
        # Invalidate exact scope prefix (tenant or tenant:profile).
        prefix = f"{tenant_id}:"
        with self._lock:
            for key in [
                k for k in self._entries if k == tenant_id or k.startswith(prefix)
            ]:
                del self._entries[key]

    def _evict_expired_locked(self, now: float) -> None:
        expired = [k for k, v in self._entries.items() if v.expires_at <= now]
        for key in expired:
            del self._entries[key]


_DEFAULT_CACHE: AgentProfileCacheProto | None = None
_DEFAULT_CACHE_LOCK = threading.Lock()


def _ttl_from_env() -> float:
    raw = os.getenv("AGENT_PROFILE_CACHE_TTL_SEC", "").strip()
    if not raw:
        return 60.0
    return float(raw)


def profile_cache_from_env() -> AgentProfileCacheProto:
    """Select Redis when REDIS_URL is set; otherwise in-process memory cache."""
    redis_url = os.getenv("REDIS_URL", "").strip()
    ttl = _ttl_from_env()
    if redis_url:
        from tenant.profile_cache_redis import RedisAgentProfileCache

        return RedisAgentProfileCache(redis_url=redis_url, ttl_sec=ttl)
    return AgentProfileCache(ttl_sec=ttl)


def default_profile_cache() -> AgentProfileCacheProto:
    """Process-wide cache singleton (memory or Redis depending on env)."""
    global _DEFAULT_CACHE
    with _DEFAULT_CACHE_LOCK:
        if _DEFAULT_CACHE is None:
            _DEFAULT_CACHE = profile_cache_from_env()
        return _DEFAULT_CACHE


def reset_default_profile_cache_for_tests() -> None:
    """Clear the process-wide default (tests only)."""
    global _DEFAULT_CACHE
    with _DEFAULT_CACHE_LOCK:
        _DEFAULT_CACHE = None
