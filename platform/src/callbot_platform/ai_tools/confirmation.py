"""HMAC confirmation tokens for AI mutations.

Flow:
  1. Mutation invoked with confirmed=false → issue token bound to
     tenant + call + tool + operation_id + args fingerprint
  2. After verbal confirm, mutation invoked with confirmed=true + token
  3. Executor verifies token; model cannot invent a valid token without step 1

Uses METADATA_HMAC_SECRET (same family as call-scope).
"""

from __future__ import annotations

import hashlib
import hmac
import json
import time
from typing import Any
from uuid import UUID

DEFAULT_TTL_SECONDS = 900


def args_fingerprint(args: dict[str, Any]) -> str:
    canonical = json.dumps(args, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def issue_confirmation_token(
    *,
    secret: str,
    tenant_id: UUID,
    call_id: UUID | None,
    tool_name: str,
    operation_id: UUID,
    args: dict[str, Any],
    ttl_seconds: int = DEFAULT_TTL_SECONDS,
) -> str:
    if not secret or not secret.strip():
        raise ValueError("HMAC secret required for confirmation tokens")
    exp = int(time.time()) + max(60, ttl_seconds)
    payload = {
        "v": 1,
        "tenant_id": str(tenant_id),
        "call_id": str(call_id) if call_id else "",
        "tool": tool_name,
        "operation_id": str(operation_id),
        "args_fp": args_fingerprint(args),
        "exp": exp,
    }
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    sig = hmac.new(
        secret.strip().encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    return f"{body}.{sig}"


def verify_confirmation_token(
    *,
    secret: str,
    token: str | None,
    tenant_id: UUID,
    call_id: UUID | None,
    tool_name: str,
    operation_id: UUID,
    args: dict[str, Any],
) -> bool:
    """Return True when the token is valid for the intended operation+args."""
    return (
        verify_confirmation_status(
            secret=secret,
            token=token,
            tenant_id=tenant_id,
            call_id=call_id,
            tool_name=tool_name,
            operation_id=operation_id,
            args=args,
        )
        == "ok"
    )


def verify_confirmation_status(
    *,
    secret: str,
    token: str | None,
    tenant_id: UUID,
    call_id: UUID | None,
    tool_name: str,
    operation_id: UUID,
    args: dict[str, Any],
) -> str:
    """Return ``ok``, ``expired``, or ``invalid`` for confirmation tokens."""
    if not token or not secret:
        return "invalid"
    try:
        body, sig = token.rsplit(".", 1)
    except ValueError:
        return "invalid"
    expected = hmac.new(
        secret.strip().encode("utf-8"),
        body.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()
    if not hmac.compare_digest(expected, sig):
        return "invalid"
    try:
        payload = json.loads(body)
    except json.JSONDecodeError:
        return "invalid"
    if int(payload.get("exp") or 0) < int(time.time()):
        return "expired"
    if payload.get("tenant_id") != str(tenant_id):
        return "invalid"
    if payload.get("tool") != tool_name:
        return "invalid"
    if payload.get("operation_id") != str(operation_id):
        return "invalid"
    expected_call = str(call_id) if call_id else ""
    if payload.get("call_id") != expected_call:
        return "invalid"
    if payload.get("args_fp") != args_fingerprint(args):
        return "invalid"
    return "ok"
