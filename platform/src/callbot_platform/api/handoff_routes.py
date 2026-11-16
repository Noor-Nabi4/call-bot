"""Handoff settings APIs."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_entitled_permission,
    require_internal_token,
)
from callbot_platform.domain.phone import PhoneNumberError
from callbot_platform.handoff.repos import HandoffError, HandoffRepository
from callbot_platform.rbac.ai_auth import require_ai_tool_permission
from callbot_platform.security.call_scope import (
    CallScope,
    enforce_body_tenant,
    optional_or_required_call_scope,
)

internal_router = APIRouter(
    prefix="/internal/handoff",
    dependencies=[Depends(require_internal_token)],
)
ops_router = APIRouter(prefix="/api/handoff")

_require_handoff_read = require_entitled_permission("handoff.read")
_require_handoff_manage = require_entitled_permission("handoff.manage")


class UpsertBody(BaseModel):
    enabled: bool | None = None
    mode: str | None = None
    escalation_phone_e164: str | None = None
    sip_outbound_trunk_id: str | None = None


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, (HandoffError, PhoneNumberError)):
        return HTTPException(
            status_code=400,
            detail={
                "code": getattr(exc, "code", "invalid"),
                "message": str(exc),
            },
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


@internal_router.get("/{tenant_id}")
def get_internal(
    tenant_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    scope: CallScope | None = Depends(optional_or_required_call_scope),  # noqa: B008
) -> dict[str, Any]:
    if scope is not None:
        enforce_body_tenant(scope, tenant_id)
    require_ai_tool_permission(session, tenant_id, "handoff")
    return {"settings": HandoffRepository(session).get(tenant_id)}


@ops_router.get("")
def get_ops(
    user: CurrentUser = Depends(_require_handoff_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"settings": HandoffRepository(session).get(user.tenant_id)}


@ops_router.put("")
def put_ops(
    body: UpsertBody,
    user: CurrentUser = Depends(_require_handoff_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        settings = HandoffRepository(session).upsert(
            user.tenant_id,
            enabled=body.enabled,
            mode=body.mode,
            escalation_phone_e164=body.escalation_phone_e164,
            sip_outbound_trunk_id=body.sip_outbound_trunk_id,
            actor=user.email,
        )
        return {"settings": settings}
    except Exception as exc:
        raise _http(exc) from exc
