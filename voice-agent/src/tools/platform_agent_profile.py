"""HTTP client for platform tenant Agent Profile."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request
from urllib.parse import urlencode

from tenant.agent_profile import AgentProfile, AgentProfileError
from tenant.profile_cache import AgentProfileCacheProto, default_profile_cache


class PlatformAgentProfileError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PlatformAgentProfileClient:
    def __init__(
        self,
        *,
        base_url: str,
        internal_token: str,
        timeout_sec: float = 5.0,
        cache: AgentProfileCacheProto | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = internal_token
        self._timeout = timeout_sec
        self._cache = cache if cache is not None else default_profile_cache()

    def get_meta(
        self, tenant_id: str, *, agent_profile_id: str | None = None
    ) -> dict[str, Any]:
        if agent_profile_id:
            path = (
                f"/internal/tenants/{tenant_id}/agent-profiles/{agent_profile_id}/meta"
            )
        else:
            path = f"/internal/tenants/{tenant_id}/agent-profile/meta"
        payload = self._get(path)
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            raise PlatformAgentProfileError(
                "agent_profile_invalid", "Profile meta payload missing"
            )
        return meta

    def get_profile(
        self,
        tenant_id: str,
        *,
        agent_profile_id: str | None = None,
        use_cache: bool = True,
    ) -> AgentProfile:
        if not tenant_id.strip():
            raise PlatformAgentProfileError(
                "agent_profile_invalid", "tenant_id is required"
            )
        cache_key = self._cache_key(tenant_id, agent_profile_id)
        if use_cache:
            cached = self._cache.get(cache_key)
            if cached is not None and cached.tenant_id == tenant_id:
                if (
                    agent_profile_id
                    and cached.agent_profile_id
                    and cached.agent_profile_id != agent_profile_id
                ):
                    self._cache.invalidate(cache_key)
                else:
                    try:
                        meta = self.get_meta(
                            tenant_id, agent_profile_id=agent_profile_id
                        )
                        remote_version = int(meta.get("profile_version") or 0)
                    except PlatformAgentProfileError:
                        self._cache.invalidate(cache_key)
                        raise
                    if remote_version == cached.profile_version:
                        return cached
                    self._cache.invalidate(cache_key)

        if agent_profile_id:
            path = f"/internal/tenants/{tenant_id}/agent-profiles/{agent_profile_id}"
        else:
            path = f"/internal/tenants/{tenant_id}/agent-profile"
            if agent_profile_id:
                path = f"{path}?{urlencode({'agent_profile_id': agent_profile_id})}"

        payload = self._get(path)
        raw = payload.get("profile")
        if not isinstance(raw, dict):
            raise PlatformAgentProfileError(
                "agent_profile_invalid", "Profile payload missing"
            )
        try:
            profile = AgentProfile.from_api_payload(raw)
        except AgentProfileError as exc:
            raise PlatformAgentProfileError(exc.code, str(exc)) from exc
        if profile.tenant_id != tenant_id:
            raise PlatformAgentProfileError(
                "agent_profile_tenant_mismatch",
                "Profile tenant_id does not match resolved tenant",
            )
        if (
            agent_profile_id
            and profile.agent_profile_id
            and profile.agent_profile_id != agent_profile_id
        ):
            raise PlatformAgentProfileError(
                "agent_profile_mismatch",
                "Loaded profile id does not match resolved agent_profile_id",
            )
        self._cache.put(profile, cache_key=cache_key)
        return profile

    def invalidate_cache(
        self, tenant_id: str, *, agent_profile_id: str | None = None
    ) -> None:
        self._cache.invalidate(self._cache_key(tenant_id, agent_profile_id))

    @staticmethod
    def _cache_key(tenant_id: str, agent_profile_id: str | None) -> str:
        if agent_profile_id:
            return f"{tenant_id}:{agent_profile_id}"
        return tenant_id

    def _get(self, path: str) -> dict[str, Any]:
        if not self._base or not self._token:
            raise PlatformAgentProfileError(
                "platform_not_configured",
                "PLATFORM_API_URL and INTERNAL_SERVICE_TOKEN are required "
                "for agent profile",
            )
        req = request.Request(
            f"{self._base}{path}",
            headers={
                "Accept": "application/json",
                "X-Internal-Token": self._token,
            },
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except TimeoutError as exc:
            raise PlatformAgentProfileError(
                "agent_profile_timeout",
                "Timed out loading agent profile",
            ) from exc
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            code = "agent_profile_error"
            message = raw
            try:
                detail = json.loads(raw).get("detail")
                if isinstance(detail, dict):
                    code = str(detail.get("code") or code)
                    message = str(detail.get("message") or message)
            except json.JSONDecodeError:
                pass
            if exc.code == 404:
                raise PlatformAgentProfileError(
                    code if code != "agent_profile_error" else "agent_profile_missing",
                    message,
                ) from exc
            if exc.code == 422:
                raise PlatformAgentProfileError(
                    code if code != "agent_profile_error" else "agent_profile_invalid",
                    message,
                ) from exc
            raise PlatformAgentProfileError(code, message) from exc
        except error.URLError as exc:
            reason = getattr(exc, "reason", None)
            if isinstance(reason, TimeoutError) or "timed out" in str(exc).lower():
                raise PlatformAgentProfileError(
                    "agent_profile_timeout",
                    "Timed out loading agent profile",
                ) from exc
            raise PlatformAgentProfileError(
                "agent_profile_unavailable",
                "Could not reach platform for agent profile",
            ) from exc


def agent_profile_client_from_env(
    *, cache: AgentProfileCacheProto | None = None
) -> PlatformAgentProfileClient:
    timeout = os.getenv("AGENT_PROFILE_TIMEOUT_SEC", "").strip()
    timeout_sec = float(timeout) if timeout else 5.0
    return PlatformAgentProfileClient(
        base_url=os.getenv("PLATFORM_API_URL", "").strip(),
        internal_token=os.getenv("INTERNAL_SERVICE_TOKEN", "").strip(),
        timeout_sec=timeout_sec,
        cache=cache if cache is not None else default_profile_cache(),
    )
