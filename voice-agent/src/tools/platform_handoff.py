"""HTTP client for tenant handoff settings."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from tools.call_scope import CallScopeMixin


class PlatformHandoffError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PlatformHandoffClient(CallScopeMixin):
    def __init__(
        self,
        *,
        base_url: str,
        internal_token: str,
        timeout_sec: float = 8.0,
        call_scope: str | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = internal_token
        self._timeout = timeout_sec
        self._call_scope = call_scope

    def get_settings(self, tenant_id: str) -> dict[str, Any]:
        if not self._base or not self._token:
            raise PlatformHandoffError(
                "platform_not_configured",
                "PLATFORM_API_URL and INTERNAL_SERVICE_TOKEN are required",
            )
        req = request.Request(
            f"{self._base}/internal/handoff/{tenant_id}",
            headers=self._scope_headers({"X-Internal-Token": self._token}),
            method="GET",
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            raise PlatformHandoffError("handoff_error", raw) from exc


def handoff_client_from_env() -> PlatformHandoffClient:
    return PlatformHandoffClient(
        base_url=os.getenv("PLATFORM_API_URL", "").strip(),
        internal_token=os.getenv("INTERNAL_SERVICE_TOKEN", "").strip(),
    )
