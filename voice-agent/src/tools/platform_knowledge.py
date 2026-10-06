"""HTTP client for platform knowledge search."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request

from tools.call_scope import CallScopeMixin


class PlatformKnowledgeError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PlatformKnowledgeClient(CallScopeMixin):
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

    def search(
        self,
        *,
        tenant_id: str,
        query: str,
        limit: int = 5,
        agent_profile_id: str | None = None,
    ) -> dict[str, Any]:
        if not self._base or not self._token:
            raise PlatformKnowledgeError(
                "platform_not_configured",
                "PLATFORM_API_URL and INTERNAL_SERVICE_TOKEN are required",
            )
        body_dict: dict[str, Any] = {
            "tenant_id": tenant_id,
            "query": query,
            "limit": limit,
        }
        if agent_profile_id:
            body_dict["agent_profile_id"] = agent_profile_id
        body = json.dumps(body_dict).encode("utf-8")
        req = request.Request(
            f"{self._base}/internal/knowledge/search",
            data=body,
            headers=self._scope_headers(
                {
                    "Content-Type": "application/json",
                    "X-Internal-Token": self._token,
                }
            ),
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            code = "knowledge_error"
            message = raw
            try:
                detail = json.loads(raw).get("detail")
                if isinstance(detail, dict):
                    code = str(detail.get("code") or code)
                    message = str(detail.get("message") or message)
            except json.JSONDecodeError:
                pass
            raise PlatformKnowledgeError(code, message) from exc


def knowledge_client_from_env() -> PlatformKnowledgeClient:
    return PlatformKnowledgeClient(
        base_url=os.getenv("PLATFORM_API_URL", "").strip(),
        internal_token=os.getenv("INTERNAL_SERVICE_TOKEN", "").strip(),
    )
