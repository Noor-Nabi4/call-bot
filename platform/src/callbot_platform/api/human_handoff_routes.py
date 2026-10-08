"""Human Handoff CRM APIs (Phase 24)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.human_handoff import HandoffDomainError, HumanHandoffService
from callbot_platform.human_handoff.departments import DepartmentService
from callbot_platform.rbac.errors import RbacError

router = APIRouter(prefix="/api/admin/crm", tags=["human-handoff"])

_require_read = require_entitled_permission("handoffs.read")
_require_manage = require_entitled_permission("handoffs.manage")
_require_accept = require_entitled_permission("handoffs.accept")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, HandoffDomainError):
        status = 404 if exc.code.endswith("_not_found") else 400
        if exc.code in {"handoff_conflict", "already_resolved"}:
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


class CreateHandoffBody(BaseModel):
    model_config = {"extra": "forbid"}
    channel: str = Field(default="VOICE", max_length=16)
    reason: str | None = Field(default=None, max_length=64)
    summary: str | None = Field(default=None, max_length=4000)
    department: str | None = Field(default=None, max_length=64)
    emergency: bool = False
    call_id: UUID | None = None
    conversation_id: UUID | None = None
    customer_id: UUID | None = None
    job_id: UUID | None = None
    appointment_id: UUID | None = None
    target_technician_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=191)


class DepartmentUpsertBody(BaseModel):
    model_config = {"extra": "forbid"}
    slug: str = Field(min_length=1, max_length=64)
    name: str = Field(min_length=1, max_length=128)
    phone_e164: str | None = Field(default=None, max_length=32)
    active: bool = True


@router.get("/handoffs")
def list_handoffs(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    status: str | None = Query(default=None),
    priority: str | None = Query(default=None),
    channel: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    try:
        return HumanHandoffService(session).list(
            user.tenant_id,
            status=status,
            priority=priority,
            channel=channel,
            limit=limit,
            offset=offset,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/handoffs")
def create_handoff(
    body: CreateHandoffBody,
    user: CurrentUser = Depends(_require_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = HumanHandoffService(session).create_request(
            tenant_id=user.tenant_id,
            channel=body.channel,
            actor=_actor(user),
            reason=body.reason,
            summary=body.summary,
            department=body.department,
            emergency=body.emergency,
            call_id=body.call_id,
            conversation_id=body.conversation_id,
            customer_id=body.customer_id,
            job_id=body.job_id,
            appointment_id=body.appointment_id,
            target_technician_id=body.target_technician_id,
            idempotency_key=body.idempotency_key,
        )
        return {"handoff": data}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/handoffs/{handoff_id}")
def get_handoff(
    handoff_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"handoff": HumanHandoffService(session).get(user.tenant_id, handoff_id)}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/handoffs/{handoff_id}/accept")
def accept_handoff(
    handoff_id: UUID,
    user: CurrentUser = Depends(_require_accept),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = HumanHandoffService(session).accept(
            user.tenant_id,
            handoff_id,
            actor=_actor(user),
            user_id=user.user_id,
        )
        return {"handoff": data}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/handoffs/{handoff_id}/reject")
def reject_handoff(
    handoff_id: UUID,
    user: CurrentUser = Depends(_require_accept),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = HumanHandoffService(session).reject(
            user.tenant_id, handoff_id, actor=_actor(user)
        )
        return {"handoff": data}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/handoffs/{handoff_id}/complete")
def complete_handoff(
    handoff_id: UUID,
    user: CurrentUser = Depends(_require_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = HumanHandoffService(session).complete(
            user.tenant_id, handoff_id, actor=_actor(user)
        )
        return {"handoff": data}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/departments")
def list_departments(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"departments": DepartmentService(session).list(user.tenant_id)}
    except Exception as exc:
        raise _http(exc) from exc


@router.put("/departments")
def upsert_department(
    body: DepartmentUpsertBody,
    user: CurrentUser = Depends(_require_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        data = DepartmentService(session).upsert(
            user.tenant_id,
            slug=body.slug,
            name=body.name,
            actor=_actor(user),
            phone_e164=body.phone_e164,
            active=body.active,
        )
        return {"department": data}
    except Exception as exc:
        raise _http(exc) from exc
