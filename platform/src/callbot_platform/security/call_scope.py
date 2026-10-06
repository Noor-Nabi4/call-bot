"""Call-scoped authorization for internal voice/telephony APIs."""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from dataclasses import dataclass
from typing import Any
from uuid import UUID

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from callbot_platform.api.deps import db_dep, require_internal_token, settings_dep
from callbot_platform.config import Settings
from callbot_platform.db.models import Call
from callbot_platform.tenancy import (
    TenantContext,
    TenantSource,
    set_tenant_context,
)


class CallScopeError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


@dataclass(frozen=True, slots=True)
class CallScope:
    """Authenticated call/tenant binding for internal APIs."""

    tenant_id: UUID
    call_id: UUID | None
    room_name: str | None
    exp: int
    iat: int

    def assert_tenant(self, tenant_id: UUID) -> None:
        if self.tenant_id != tenant_id:
            raise CallScopeError(
                "tenant_mismatch",
                "Call scope tenant does not match requested tenant",
            )

    def assert_call(self, call_id: UUID) -> None:
        if self.call_id is None:
            raise CallScopeError(
                "call_required",
                "This operation requires a call-bound scope token",
            )
        if self.call_id != call_id:
            raise CallScopeError(
                "call_mismatch",
                "Call scope call_id does not match requested call",
            )


class CallScopeSigner:
    """HMAC call-scope tokens (reuse METADATA_HMAC_SECRET)."""

    def __init__(self, secret: str) -> None:
        if not secret or not secret.strip():
            raise ValueError("METADATA_HMAC_SECRET is required for call scope")
        self._secret = secret.strip().encode("utf-8")

    def issue(
        self,
        *,
        tenant_id: UUID,
        call_id: UUID | None = None,
        room_name: str | None = None,
        ttl_seconds: int = 14_400,
    ) -> str:
        now = int(time.time())
        payload: dict[str, Any] = {
            "v": 1,
            "tenant_id": str(tenant_id),
            "iat": now,
            "exp": now + int(ttl_seconds),
        }
        if call_id is not None:
            payload["call_id"] = str(call_id)
        if room_name:
            payload["room_name"] = room_name
        return self._sign(payload)

    def verify(self, raw: str | None) -> CallScope:
        if not raw or not raw.strip():
            raise CallScopeError("missing_claim", "X-Call-Scope header is required")
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise CallScopeError("invalid_claim", "Malformed call scope") from exc
        if not isinstance(data, dict):
            raise CallScopeError("invalid_claim", "Malformed call scope")
        provided = data.get("sig")
        if not provided or not isinstance(provided, str):
            raise CallScopeError("invalid_claim", "Call scope missing signature")
        body = {k: v for k, v in data.items() if k != "sig"}
        canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
        expected = hmac.new(
            self._secret, canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        if not hmac.compare_digest(provided, expected):
            raise CallScopeError("tampered_claim", "Call scope signature mismatch")

        now = int(time.time())
        try:
            exp = int(body["exp"])
            iat = int(body["iat"])
            tenant_id = UUID(str(body["tenant_id"]))
        except (KeyError, TypeError, ValueError) as exc:
            raise CallScopeError("invalid_claim", "Call scope missing fields") from exc
        if exp < now:
            raise CallScopeError("expired_claim", "Call scope has expired")
        if iat > now + 60:
            raise CallScopeError("invalid_claim", "Call scope iat is in the future")

        call_id = None
        if body.get("call_id"):
            try:
                call_id = UUID(str(body["call_id"]))
            except ValueError as exc:
                raise CallScopeError("invalid_claim", "Invalid call_id") from exc

        room_name = body.get("room_name")
        if room_name is not None and not isinstance(room_name, str):
            raise CallScopeError("invalid_claim", "Invalid room_name")

        return CallScope(
            tenant_id=tenant_id,
            call_id=call_id,
            room_name=room_name,
            exp=exp,
            iat=iat,
        )

    def _sign(self, payload: dict[str, Any]) -> str:
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
        sig = hmac.new(
            self._secret, canonical.encode("utf-8"), hashlib.sha256
        ).hexdigest()
        out = dict(payload)
        out["sig"] = sig
        return json.dumps(out, separators=(",", ":"))


def require_call_scope(
    request: Request,
    _: None = Depends(require_internal_token),
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    x_call_scope: str | None = Header(default=None, alias="X-Call-Scope"),
) -> CallScope:
    """
    Require internal token + X-Call-Scope when REQUIRE_CALL_SCOPE=true.

    When REQUIRE_CALL_SCOPE=false (local migration only), still requires the
    header if present; if absent, raises missing_claim so new clients always
    send scope. Prefer enabling the flag in all environments.
    """
    _ = request  # reserved for request.state binding
    try:
        if not settings.metadata_hmac_secret:
            raise ValueError("METADATA_HMAC_SECRET is required for call scope")
        if not settings.require_call_scope and not x_call_scope:
            raise CallScopeError(
                "missing_claim",
                "X-Call-Scope header is required (shared token alone is denied)",
            )
        signer = CallScopeSigner(settings.metadata_hmac_secret)
        scope = signer.verify(x_call_scope)
    except CallScopeError as exc:
        raise HTTPException(
            status_code=401, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=500,
            detail={"code": "scope_misconfigured", "message": str(exc)},
        ) from exc

    if scope.call_id is not None:
        call = session.get(Call, scope.call_id)
        if call is None:
            raise HTTPException(
                status_code=401,
                detail={"code": "invalid_call", "message": "Call not found for scope"},
            )
        if call.tenant_id != scope.tenant_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "tenant_mismatch",
                    "message": "Call does not belong to scoped tenant",
                },
            )

    set_tenant_context(
        TenantContext(tenant_id=scope.tenant_id, source=TenantSource.INTERNAL)
    )
    request.state.call_scope = scope
    return scope


def enforce_body_tenant(scope: CallScope, tenant_id: UUID) -> None:
    try:
        scope.assert_tenant(tenant_id)
    except CallScopeError as exc:
        raise HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        ) from exc


def enforce_body_call(scope: CallScope, call_id: UUID) -> None:
    try:
        scope.assert_call(call_id)
    except CallScopeError as exc:
        raise HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        ) from exc


def optional_or_required_call_scope(
    request: Request,
    _: None = Depends(require_internal_token),
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    x_call_scope: str | None = Header(default=None, alias="X-Call-Scope"),
) -> CallScope | None:
    """
    When REQUIRE_CALL_SCOPE=true, shared token alone is denied (missing claim → 401).
    When false, scope is optional (legacy tests); still verified if header present.
    """
    if not settings.require_call_scope and not x_call_scope:
        return None
    return require_call_scope(request, _, session, settings, x_call_scope)
