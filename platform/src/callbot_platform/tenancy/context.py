"""Request-scoped tenant context (never trust client-supplied tenant alone)."""

from __future__ import annotations

from contextvars import ContextVar, Token
from dataclasses import dataclass
from enum import StrEnum
from uuid import UUID


class TenantSource(StrEnum):
    SESSION = "session"
    API_KEY = "api_key"
    SIP = "sip"
    INTERNAL = "internal"
    JOB = "job"
    TEST = "test"


@dataclass(frozen=True, slots=True)
class TenantContext:
    """Authenticated tenant boundary for the current request or job."""

    tenant_id: UUID
    source: TenantSource


_tenant_ctx: ContextVar[TenantContext | None] = ContextVar(
    "callbot_tenant_context", default=None
)


def get_tenant_context() -> TenantContext | None:
    return _tenant_ctx.get()


def require_tenant_context() -> TenantContext:
    ctx = _tenant_ctx.get()
    if ctx is None:
        raise RuntimeError("Tenant context is not set for this request or job")
    return ctx


def set_tenant_context(ctx: TenantContext) -> Token[TenantContext | None]:
    return _tenant_ctx.set(ctx)


def clear_tenant_context(token: Token[TenantContext | None] | None = None) -> None:
    if token is not None:
        _tenant_ctx.reset(token)
    else:
        _tenant_ctx.set(None)
