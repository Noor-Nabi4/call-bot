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
    require_internal_token,
    require_entitled_ops_roles,
)
from callbot_platform.domain.phone import PhoneNumberError
from callbot_platform.handoff.repos import HandoffError, HandoffRepository
from callbot_platform.security.session import ROLE_ADMIN, ROLE_DISPATCHER

internal_router = APIRouter(
    prefix="/internal/handoff",
    dependencies=[Depends(require_internal_token)],
)
ops_router = APIRouter(prefix="/api/handoff")


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
    tenant_id: UUID, session: Session = Depends(db_dep)
) -> dict[str, Any]:
    return {"settings": HandoffRepository(session).get(tenant_id)}


@ops_router.get("")
def get_ops(
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)),
    session: Session = Depends(db_dep),
) -> dict[str, Any]:
    return {"settings": HandoffRepository(session).get(user.tenant_id)}


@ops_router.put("")
def put_ops(
    body: UpsertBody,
    user: CurrentUser = Depends(require_entitled_ops_roles(ROLE_ADMIN, ROLE_DISPATCHER)),
    session: Session = Depends(db_dep),
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
