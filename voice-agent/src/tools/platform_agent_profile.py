"""HTTP client for platform tenant Agent Profile."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

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

    def get_meta(self, tenant_id: str) -> dict[str, Any]:
        payload = self._get(f"/internal/tenants/{tenant_id}/agent-profile/meta")
        meta = payload.get("meta")
        if not isinstance(meta, dict):
            raise PlatformAgentProfileError(
                "agent_profile_invalid", "Profile meta payload missing"
            )
        return meta

    def get_profile(self, tenant_id: str, *, use_cache: bool = True) -> AgentProfile:
        if not tenant_id.strip():
            raise PlatformAgentProfileError(
                "agent_profile_invalid", "tenant_id is required"
            )
        if use_cache:
            cached = self._cache.get(tenant_id)
            if cached is not None and cached.tenant_id == tenant_id:
                try:
                    meta = self.get_meta(tenant_id)
                    remote_version = int(meta.get("profile_version") or 0)
                except PlatformAgentProfileError:
                    self._cache.invalidate(tenant_id)
                    raise
                if remote_version == cached.profile_version:
                    return cached
                # Configuration changed — drop stale entry before full reload.
                self._cache.invalidate(tenant_id)

        payload = self._get(f"/internal/tenants/{tenant_id}/agent-profile")
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
        self._cache.put(profile)
        return profile

    def invalidate_cache(self, tenant_id: str) -> None:
        self._cache.invalidate(tenant_id)

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
