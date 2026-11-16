"""Process-local cache for immutable geo catalog payloads."""

from __future__ import annotations

import time
from typing import Any

_CATALOG_TTL_SEC = 300.0
_catalog_payload: dict[str, Any] | None = None
_catalog_expires_at = 0.0


def get_cached_catalog() -> dict[str, Any] | None:
    if _catalog_payload is None:
        return None
    if time.monotonic() >= _catalog_expires_at:
        return None
    return _catalog_payload


def set_cached_catalog(
    payload: dict[str, Any], *, ttl_sec: float = _CATALOG_TTL_SEC
) -> None:
    global _catalog_payload, _catalog_expires_at
    _catalog_payload = payload
    _catalog_expires_at = time.monotonic() + max(ttl_sec, 0.0)


def clear_catalog_cache() -> None:
    global _catalog_payload, _catalog_expires_at
    _catalog_payload = None
    _catalog_expires_at = 0.0
