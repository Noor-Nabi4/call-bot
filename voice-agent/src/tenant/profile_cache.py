"""Short-lived in-process cache for tenant Agent Profiles."""

from __future__ import annotations

import threading
import time
from dataclasses import dataclass

from tenant.agent_profile import AgentProfile


@dataclass(frozen=True, slots=True)
class _CacheEntry:
    profile: AgentProfile
    expires_at: float


class AgentProfileCache:
    """Bounded TTL cache keyed by tenant_id + profile_version.

    Never shares entries across tenants. Expired entries are not returned.
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
    def _key(tenant_id: str, profile_version: int | None = None) -> str:
        if profile_version is None:
            return f"{tenant_id}:latest"
        return f"{tenant_id}:v{profile_version}"

    def get(
        self, tenant_id: str, *, profile_version: int | None = None
    ) -> AgentProfile | None:
        key = self._key(tenant_id, profile_version)
        now = time.monotonic()
        with self._lock:
            entry = self._entries.get(key)
            if entry is None:
                return None
            if entry.expires_at <= now:
                del self._entries[key]
                return None
            # Never serve a profile for a different tenant key.
            if entry.profile.tenant_id != tenant_id:
                del self._entries[key]
                return None
            if (
                profile_version is not None
                and entry.profile.profile_version != profile_version
            ):
                del self._entries[key]
                return None
            return entry.profile

    def put(self, profile: AgentProfile) -> None:
        now = time.monotonic()
        expires_at = now + self._ttl_sec
        versioned = self._key(profile.tenant_id, profile.profile_version)
        latest = self._key(profile.tenant_id, None)
        entry = _CacheEntry(profile=profile, expires_at=expires_at)
        with self._lock:
            self._entries[versioned] = entry
            self._entries[latest] = entry
            self._evict_expired_locked(now)
            while len(self._entries) > self._max_entries:
                # Drop an arbitrary oldest-ish key (dict preserves insertion order).
                oldest = next(iter(self._entries))
                del self._entries[oldest]

    def invalidate(self, tenant_id: str) -> None:
        prefix = f"{tenant_id}:"
        with self._lock:
            for key in [k for k in self._entries if k.startswith(prefix)]:
                del self._entries[key]

    def _evict_expired_locked(self, now: float) -> None:
        expired = [k for k, v in self._entries.items() if v.expires_at <= now]
        for key in expired:
            del self._entries[key]


# Process-wide cache for call-start latency; TTL keeps config reasonably fresh.
_DEFAULT_CACHE = AgentProfileCache(ttl_sec=60.0)


def default_profile_cache() -> AgentProfileCache:
    return _DEFAULT_CACHE
