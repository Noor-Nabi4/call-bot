"""HTTP client for platform scheduling internal APIs."""

from __future__ import annotations

import json
import os
from typing import Any
from urllib import error, request


class PlatformSchedulingError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class PlatformSchedulingClient:
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

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        if not self._base or not self._token:
            raise PlatformSchedulingError(
                "platform_not_configured",
                "PLATFORM_API_URL and INTERNAL_SERVICE_TOKEN are required "
                "for scheduling tools",
            )
        data = None
        headers = {"X-Internal-Token": self._token}
        if payload is not None:
            data = json.dumps(payload).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = request.Request(
            f"{self._base}{path}",
            data=data,
            headers=headers,
            method=method,
        )
        try:
            with request.urlopen(req, timeout=self._timeout) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except error.HTTPError as exc:
            raw = exc.read().decode("utf-8", errors="replace")
            code = "scheduling_error"
            message = raw
            try:
                detail = json.loads(raw).get("detail")
                if isinstance(detail, dict):
                    code = str(detail.get("code") or code)
                    message = str(detail.get("message") or message)
            except json.JSONDecodeError:
                pass
            raise PlatformSchedulingError(code, message) from exc

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return self._request("POST", path, payload)

    def list_slots(
        self,
        *,
        tenant_id: str,
        from_date: str | None = None,
        to_date: str | None = None,
        limit: int = 20,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {"tenant_id": tenant_id, "limit": limit}
        if from_date:
            payload["from_date"] = from_date
        if to_date:
            payload["to_date"] = to_date
        return self._post("/internal/scheduling/slots", payload)

    def book_appointment(
        self,
        *,
        tenant_id: str,
        customer_id: str,
        starts_at: str,
        service_type: str,
        notes: str | None = None,
        lead_id: str | None = None,
        call_id: str | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._post(
            "/internal/scheduling/appointments",
            {
                "tenant_id": tenant_id,
                "customer_id": customer_id,
                "starts_at": starts_at,
                "service_type": service_type,
                "notes": notes,
                "lead_id": lead_id,
                "call_id": call_id,
                "idempotency_key": idempotency_key,
            },
        )

    def reschedule_appointment(
        self,
        *,
        tenant_id: str,
        appointment_id: str,
        starts_at: str,
    ) -> dict[str, Any]:
        return self._post(
            f"/internal/scheduling/appointments/{appointment_id}/reschedule",
            {"tenant_id": tenant_id, "starts_at": starts_at},
        )

    def cancel_appointment(
        self,
        *,
        tenant_id: str,
        appointment_id: str,
    ) -> dict[str, Any]:
        return self._post(
            f"/internal/scheduling/appointments/{appointment_id}/cancel",
            {"tenant_id": tenant_id},
        )


def scheduling_client_from_env() -> PlatformSchedulingClient:
    return PlatformSchedulingClient(
        base_url=os.getenv("PLATFORM_API_URL", "").strip(),
        internal_token=os.getenv("INTERNAL_SERVICE_TOKEN", "").strip(),
    )
