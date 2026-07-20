"""Redis-backed Agent Profile cache shared across LiveKit job processes."""

from __future__ import annotations

import contextlib
import json
import logging
import threading
from typing import Any

from tenant.agent_profile import AgentProfile, AgentProfileError

logger = logging.getLogger("voice-agent.profile_cache")

KEY_PREFIX = "callbot:va:agent_profile"


class RedisAgentProfileCache:
    """Shared TTL cache for tenant Agent Profiles.

    Soft-fails on Redis errors: get returns None, put/invalidate no-op.
    Calls must not fail because Redis is unavailable.
    """

    def __init__(
        self,
        *,
        redis_url: str,
        ttl_sec: float = 60.0,
        client: Any | None = None,
    ) -> None:
        if ttl_sec <= 0:
            raise ValueError("ttl_sec must be positive")
        if not redis_url.strip() and client is None:
            raise ValueError("redis_url is required")
        self._ttl_sec = int(ttl_sec) if ttl_sec >= 1 else 1
        self._redis_url = redis_url.strip()
        self._client = client
        self._client_lock = threading.Lock()
        self._warned_error = False

    def _get_client(self) -> Any | None:
        if self._client is not None:
            return self._client
        with self._client_lock:
            if self._client is not None:
                return self._client
            try:
                import redis

                self._client = redis.Redis.from_url(
                    self._redis_url,
                    decode_responses=True,
                    socket_connect_timeout=1.0,
                    socket_timeout=1.0,
                )
                # Validate connectivity once; soft-fail if down.
                self._client.ping()
            except Exception:
                self._warn_once("redis_profile_cache_unavailable")
                self._client = None
                return None
            return self._client

    def _warn_once(self, event: str) -> None:
        if self._warned_error:
            return
        self._warned_error = True
        logger.warning(event, extra={"redis_url_host": self._safe_host()})

    def _safe_host(self) -> str:
        # Avoid logging credentials from REDIS_URL.
        try:
            from urllib.parse import urlparse

            parsed = urlparse(self._redis_url)
            host = parsed.hostname or "unknown"
            port = parsed.port
            return f"{host}:{port}" if port else host
        except Exception:
            return "unknown"

    @staticmethod
    def _key(
        tenant_id: str,
        profile_version: int | None = None,
        *,
        agent_profile_id: str | None = None,
    ) -> str:
        scope = f"{tenant_id}:{agent_profile_id}" if agent_profile_id else tenant_id
        if profile_version is None:
            return f"{KEY_PREFIX}:{scope}:latest"
        return f"{KEY_PREFIX}:{scope}:v{profile_version}"

    def get(
        self, tenant_id: str, *, profile_version: int | None = None
    ) -> AgentProfile | None:
        if not tenant_id.strip():
            return None
        client = self._get_client()
        if client is None:
            return None
        # tenant_id may be composite cache key tenant:profile_id
        if ":" in tenant_id and not tenant_id.startswith(KEY_PREFIX):
            parts = tenant_id.split(":", 1)
            scope_tenant, scope_profile = parts[0], parts[1]
            key = self._key(
                scope_tenant, profile_version, agent_profile_id=scope_profile
            )
            tenant_only = scope_tenant
        else:
            key = self._key(tenant_id, profile_version)
            tenant_only = tenant_id
        try:
            raw = client.get(key)
        except Exception:
            self._warn_once("redis_profile_cache_get_failed")
            return None
        if not raw:
            return None
        try:
            payload = json.loads(raw)
            if not isinstance(payload, dict):
                return None
            profile = AgentProfile.from_api_payload(payload)
        except (json.JSONDecodeError, AgentProfileError, TypeError, ValueError):
            self._warn_once("redis_profile_cache_corrupt")
            with contextlib.suppress(Exception):
                client.delete(key)
            return None
        if profile.tenant_id != tenant_only:
            with contextlib.suppress(Exception):
                client.delete(key)
            return None
        if profile_version is not None and profile.profile_version != profile_version:
            return None
        return profile

    def put(self, profile: AgentProfile, *, cache_key: str | None = None) -> None:
        client = self._get_client()
        if client is None:
            return
        payload = json.dumps(profile.to_api_payload(), separators=(",", ":"))
        if cache_key and ":" in cache_key:
            scope_tenant, scope_profile = cache_key.split(":", 1)
            versioned = self._key(
                scope_tenant,
                profile.profile_version,
                agent_profile_id=scope_profile,
            )
            latest = self._key(scope_tenant, None, agent_profile_id=scope_profile)
        else:
            versioned = self._key(
                profile.tenant_id,
                profile.profile_version,
                agent_profile_id=profile.agent_profile_id,
            )
            latest = self._key(
                profile.tenant_id,
                None,
                agent_profile_id=profile.agent_profile_id,
            )
        try:
            pipe = client.pipeline()
            pipe.set(versioned, payload, ex=self._ttl_sec)
            pipe.set(latest, payload, ex=self._ttl_sec)
            pipe.execute()
        except Exception:
            self._warn_once("redis_profile_cache_put_failed")

    def invalidate(self, tenant_id: str) -> None:
        if not tenant_id.strip():
            return
        client = self._get_client()
        if client is None:
            return
        pattern = f"{KEY_PREFIX}:{tenant_id}:*"
        try:
            keys: list[str] = []
            for key in client.scan_iter(match=pattern, count=64):
                keys.append(key)
            if keys:
                client.delete(*keys)
        except Exception:
            self._warn_once("redis_profile_cache_invalidate_failed")
