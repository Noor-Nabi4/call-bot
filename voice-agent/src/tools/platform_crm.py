"""HTTP client for platform CRM internal APIs."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request


class PlatformCrmError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PlatformCrmClient:
    def __init__(
        self,
        *,
        base_url: str,
        internal_token: str,
        timeout_sec: float = 8.0,
    ) -> None:
        self._base = base_url.rstrip("/")
        self._token = internal_token
        self._timeout = timeout_sec

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        if not self._base or not self._token:
            raise PlatformCrmError(
                "platform_not_configured",
                "PLATFORM_API_URL and INTERNAL_SERVICE_TOKEN are required for CRM tools",
            )
        body = json.dumps(payload).encode("utf-8")
        req = request.Request(
            f"{self._base}{path}",
            data=body,
            headers={
                "Content-Type": "application/json",
                "X-Internal-Token": self._token,
            },
            method="POST",
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            code = "crm_error"
            message = raw
            try:
                detail = json.loads(raw).get("detail")
                if isinstance(detail, dict):
                    code = str(detail.get("code") or code)
                    message = str(detail.get("message") or message)
            except json.JSONDecodeError:
                pass
            raise PlatformCrmError(code, message) from exc

    def lookup_customer(self, *, tenant_id: str, phone: str) -> dict[str, Any]:
        return self._post(
            "/internal/crm/customers/lookup",
            {"tenant_id": tenant_id, "phone": phone},
        )

    def upsert_customer(
        self,
        *,
        tenant_id: str,
        name: str,
        phone: str,
        email: str | None = None,
        address: str | None = None,
    ) -> dict[str, Any]:
        return self._post(
            "/internal/crm/customers/upsert",
            {
                "tenant_id": tenant_id,
                "name": name,
                "phone": phone,
                "email": email,
                "address": address,
            },
        )

    def create_lead(
        self,
        *,
        tenant_id: str,
        customer_id: str,
        service_type: str,
        urgency: str = "normal",
        notes: str | None = None,
        preferred_time_window: str | None = None,
        call_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._post(
            "/internal/crm/leads",
            {
                "tenant_id": tenant_id,
                "customer_id": customer_id,
                "service_type": service_type,
                "urgency": urgency,
                "notes": notes,
                "preferred_time_window": preferred_time_window,
                "call_id": call_id,
                "idempotency_key": idempotency_key,
            },
        )

    def start_call(self, **payload: Any) -> dict[str, Any]:
        return self._post("/internal/crm/calls/start", payload)

    def end_call(self, **payload: Any) -> dict[str, Any]:
        return self._post("/internal/crm/calls/end", payload)


def crm_client_from_env() -> PlatformCrmClient:
    return PlatformCrmClient(
        base_url=os.getenv("PLATFORM_API_URL", "").strip(),
        internal_token=os.getenv("INTERNAL_SERVICE_TOKEN", "").strip(),
    )
