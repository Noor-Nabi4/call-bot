"""HTTP client for platform Phase 14 AI tool executor."""

from __future__ import annotations

import json
import os
import time
import uuid
from typing import Any
from urllib import error, request

from tools.call_scope import CallScopeMixin

# Align with platform TimeoutClass.MUTATION / EXTERNAL_PROVIDER budgets.
_DEFAULT_TIMEOUT_SEC = float(os.getenv("AI_TOOLS_HTTP_TIMEOUT_SEC", "12") or "12")
_MAX_READ_ATTEMPTS = 2
_MAX_MUTATION_ATTEMPTS = 2
_NON_RETRYABLE = frozenset(
    {
        "invalid_arguments",
        "permission_denied",
        "tenant_access_denied",
        "not_found",
        "ambiguous_result",
        "customer_not_found",
        "customer_already_exists",
        "service_not_found",
        "product_not_found",
        "variant_not_found",
        "inventory_unavailable",
        "price_unavailable",
        "availability_empty",
        "booking_conflict",
        "booking_invalid",
        "order_conflict",
        "order_invalid",
        "idempotency_conflict",
        "operation_already_completed",
        "confirmation_required",
        "expired",
        "archived",
        "handoff_unavailable",
    }
)


class PlatformAiToolsError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PlatformAiToolsClient(CallScopeMixin):
    def __init__(
        self,
        *,
        base_url: str,
        internal_token: str,
        timeout_sec: float = _DEFAULT_TIMEOUT_SEC,
        call_scope: str | None = None,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = internal_token
        self._timeout = timeout_sec
        self._call_scope = call_scope

    def invoke(
        self,
        tool_name: str,
        *,
        args: dict[str, Any] | None = None,
        confirmed: bool = False,
        confirmation_token: str | None = None,
        operation_id: str | None = None,
        customer_id: str | None = None,
        caller_phone: str | None = None,
        tenant_id: str | None = None,
        mutation: bool = False,
    ) -> dict[str, Any]:
        if not self._base or not self._token:
            raise PlatformAiToolsError(
                "platform_not_configured",
                "PLATFORM_API_URL and INTERNAL_SERVICE_TOKEN are required",
            )
        payload: dict[str, Any] = {
            "args": args or {},
            "confirmed": confirmed,
        }
        if confirmation_token:
            payload["confirmation_token"] = confirmation_token
        if operation_id:
            payload["operation_id"] = operation_id
        if customer_id:
            payload["customer_id"] = customer_id
        if caller_phone:
            payload["caller_phone"] = caller_phone
        if tenant_id and not self._call_scope:
            payload["tenant_id"] = tenant_id

        attempts = _MAX_MUTATION_ATTEMPTS if mutation else _MAX_READ_ATTEMPTS
        last_exc: Exception | None = None
        for attempt in range(attempts):
            try:
                return self._post(f"/internal/ai/tools/{tool_name}", payload)
            except PlatformAiToolsError as exc:
                last_exc = exc
                if exc.code in _NON_RETRYABLE or attempt + 1 >= attempts:
                    raise
                time.sleep(0.05 * (attempt + 1))
            except error.URLError as exc:
                last_exc = PlatformAiToolsError("system_unavailable", str(exc))
                if attempt + 1 >= attempts:
                    raise last_exc from exc
                time.sleep(0.05 * (attempt + 1))
        assert last_exc is not None
        raise last_exc

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload).encode("utf-8")
        headers = self._scope_headers(
            {
                "Content-Type": "application/json",
                "X-Internal-Token": self._token,
            }
        )
        req = request.Request(
            f"{self._base}{path}",
            data=body,
            headers=headers,
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            code = "ai_tool_error"
            message = raw
            try:
                detail = json.loads(raw).get("detail")
                if isinstance(detail, dict):
                    code = str(detail.get("code") or code)
                    message = str(detail.get("message") or message)
            except json.JSONDecodeError:
                pass
            raise PlatformAiToolsError(code, message) from exc


def ai_tools_client_from_env() -> PlatformAiToolsClient:
    return PlatformAiToolsClient(
        base_url=os.getenv("PLATFORM_API_URL", "").strip(),
        internal_token=os.getenv("INTERNAL_SERVICE_TOKEN", "").strip(),
    )


def new_operation_id() -> str:
    return str(uuid.uuid4())
