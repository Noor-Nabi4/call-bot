"""Tenant-scoped in-process cache for Effective CRM configuration.

Authorization is never cached here — only schema/metadata.
Redis is not required; when unavailable/missing this cache is process-local.
On process restart the cache is empty (safe fail-open to Postgres).
"""

from __future__ import annotations

import threading
import time
from typing import Any
from uuid import UUID

from callbot_platform.tenancy.isolation import tenant_cache_key

_DEFAULT_TTL_SECONDS = 60.0
_lock = threading.RLock()
_store: dict[str, tuple[float, dict[str, Any]]] = {}


def _key(tenant_id: UUID) -> str:
    return tenant_cache_key(tenant_id, "crm", "effective_configuration")


def get_cached_effective(tenant_id: UUID) -> dict[str, Any] | None:
    key = _key(tenant_id)
    now = time.monotonic()
    with _lock:
        entry = _store.get(key)
        if entry is None:
            return None
        expires_at, payload = entry
        if expires_at < now:
            del _store[key]
            return None
        return payload


def set_cached_effective(
    tenant_id: UUID,
    payload: dict[str, Any],
    *,
    ttl_seconds: float = _DEFAULT_TTL_SECONDS,
) -> None:
    key = _key(tenant_id)
    with _lock:
        _store[key] = (time.monotonic() + max(1.0, ttl_seconds), payload)


def invalidate_effective_configuration(tenant_id: UUID) -> None:
    """Drop cached effective CRM config for one tenant."""
    key = _key(tenant_id)
    with _lock:
        _store.pop(key, None)


def clear_all_effective_configuration_cache() -> None:
    """Test helper — clear entire process cache."""
    with _lock:
        _store.clear()
