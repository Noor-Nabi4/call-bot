"""Admin Lead CRM APIs (Phase 8)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.leads import LeadService
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.service import AuthorizationService

router = APIRouter(prefix="/api/admin/crm", tags=["leads"])

_require_read = require_entitled_permission("leads.read")
_require_create = require_entitled_permission("leads.create")
_require_update = require_entitled_permission("leads.update")
_require_delete = require_entitled_permission("leads.delete")
_require_assign = require_entitled_permission("leads.assign")
_require_transition = require_entitled_permission("leads.transition")
_require_convert = require_entitled_permission("leads.convert")
_require_notes_read = require_entitled_permission("leads.notes.read")
_require_notes_create = require_entitled_permission("leads.notes.create")
_require_notes_update = require_entitled_permission("leads.notes.update")
_require_notes_delete = require_entitled_permission("leads.notes.delete")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403,
            detail={"code": exc.code, "message": str(exc)},
        )
    if isinstance(exc, CrmError):
        status = 404 if exc.code == "not_found" else 400
        if exc.code == "forbidden":
            status = 403
        if exc.code in {
            "invalid_transition",
            "lead_archived",
            "note_archived",
            "use_transition",
            "phone_conflict",
            "convert_conflict",
            "code_conflict",
            "owner_inactive",
            "customer_not_found",
            "service_not_found",
            "product_not_found",
            "owner_not_found",
            "call_not_found",
        }:
            status = 404 if exc.code.endswith("_not_found") else 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, IntegrityError):
        return HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Conflicting write"},
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


class LeadCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    title: str = Field(min_length=1, max_length=255)
    description: str | None = None
    source: str | None = Field(default=None, max_length=32)
    priority: str | None = Field(default=None, max_length=32)
    customer_id: UUID | None = None
    service_id: UUID | None = None
    product_id: UUID | None = None
    owner_user_id: UUID | None = None
    prospect_name: str | None = Field(default=None, max_length=255)
    prospect_phone: str | None = Field(default=None, max_length=32)
    prospect_email: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    preferred_time_window: str | None = Field(default=None, max_length=255)
    idempotency_key: str | None = Field(default=None, max_length=128)


class LeadUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    clear_description: bool = False
    source: str | None = Field(default=None, max_length=32)
    priority: str | None = Field(default=None, max_length=32)
    customer_id: UUID | None = None
    clear_customer: bool = False
    service_id: UUID | None = None
    clear_service: bool = False
    product_id: UUID | None = None
    clear_product: bool = False
    owner_user_id: UUID | None = None
    clear_owner: bool = False
    prospect_name: str | None = Field(default=None, max_length=255)
    prospect_phone: str | None = Field(default=None, max_length=32)
    prospect_email: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    preferred_time_window: str | None = Field(default=None, max_length=255)
    # Rejected server-side if present via forbid — status must use transition.
    status: str | None = Field(default=None, max_length=32)


class TransitionBody(BaseModel):
    model_config = {"extra": "forbid"}
    to_status: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=500)


class ConvertBody(BaseModel):
    model_config = {"extra": "forbid"}
    customer_id: UUID | None = None
    create_customer: dict[str, Any] | None = None


class NoteCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    body: str = Field(min_length=1, max_length=20000)


class NoteUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    body: str = Field(min_length=1, max_length=20000)


@router.get("/leads")
def list_leads(
    q: str | None = None,
    status: str | None = None,
    priority: str | None = None,
    source: str | None = None,
    owner_user_id: UUID | None = None,
    customer_id: UUID | None = None,
    service_id: UUID | None = None,
    product_id: UUID | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    updated_from: datetime | None = None,
    updated_to: datetime | None = None,
    include_archived: bool = False,
    limit: int | None = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return LeadService(session).list(
            user.tenant_id,
            q=q,
            status=status,
            priority=priority,
            source=source,
            owner_user_id=owner_user_id,
            customer_id=customer_id,
            service_id=service_id,
            product_id=product_id,
            created_from=created_from,
            created_to=created_to,
            updated_from=updated_from,
            updated_to=updated_to,
            include_archived=include_archived,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/leads/pipeline/counts")
def pipeline_counts(
    owner_user_id: UUID | None = None,
    source: str | None = None,
    priority: str | None = None,
    include_archived: bool = False,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return LeadService(session).pipeline_counts(
            user.tenant_id,
            owner_user_id=owner_user_id,
            source=source,
            priority=priority,
            include_archived=include_archived,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/leads", status_code=201)
def create_lead(
    body: LeadCreateBody,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        payload = body.model_dump()
        # Assignment requires leads.assign when owner is set on create.
        if body.owner_user_id is not None:
            AuthorizationService(session).require_permission(
                user.tenant_id, user.user_id, "leads.assign"
            )
        lead = LeadService(session).create(
            user.tenant_id,
            actor=_actor(user),
            actor_user_id=user.user_id,
            **payload,
        )
        return {"lead": lead}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/leads/{lead_id}")
def get_lead(
    lead_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"lead": LeadService(session).get(user.tenant_id, lead_id)}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/leads/{lead_id}")
def update_lead(
    lead_id: UUID,
    body: LeadUpdateBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        if body.owner_user_id is not None or body.clear_owner:
            AuthorizationService(session).require_permission(
                user.tenant_id, user.user_id, "leads.assign"
            )
        lead = LeadService(session).update(
            user.tenant_id,
            lead_id,
            actor=_actor(user),
            actor_user_id=user.user_id,
            **body.model_dump(exclude_unset=True),
        )
        return {"lead": lead}
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/leads/{lead_id}")
def archive_lead(
    lead_id: UUID,
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        lead = LeadService(session).archive(
            user.tenant_id,
            lead_id,
            actor=_actor(user),
            actor_user_id=user.user_id,
        )
        return {"lead": lead}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/leads/{lead_id}/restore")
def restore_lead(
    lead_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        lead = LeadService(session).restore(
            user.tenant_id,
            lead_id,
            actor=_actor(user),
            actor_user_id=user.user_id,
        )
        return {"lead": lead}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/leads/{lead_id}/transition")
def transition_lead(
    lead_id: UUID,
    body: TransitionBody,
    user: CurrentUser = Depends(_require_transition),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        lead = LeadService(session).transition_status(
            user.tenant_id,
            lead_id,
            to_status=body.to_status,
            actor=_actor(user),
            actor_user_id=user.user_id,
            reason=body.reason,
        )
        return {"lead": lead}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/leads/{lead_id}/convert")
def convert_lead(
    lead_id: UUID,
    body: ConvertBody,
    user: CurrentUser = Depends(_require_convert),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        result = LeadService(session).convert(
            user.tenant_id,
            lead_id,
            actor=_actor(user),
            actor_user_id=user.user_id,
            customer_id=body.customer_id,
            create_customer=body.create_customer,
        )
        return result
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/leads/{lead_id}/activities")
def list_activities(
    lead_id: UUID,
    limit: int | None = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return LeadService(session).list_activities(
            user.tenant_id, lead_id, limit=limit, cursor=cursor
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/leads/{lead_id}/notes")
def list_notes(
    lead_id: UUID,
    include_archived: bool = False,
    limit: int | None = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    user: CurrentUser = Depends(_require_notes_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return LeadService(session).notes.list(
            user.tenant_id,
            lead_id,
            include_archived=include_archived,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/leads/{lead_id}/notes", status_code=201)
def create_note(
    lead_id: UUID,
    body: NoteCreateBody,
    user: CurrentUser = Depends(_require_notes_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        note = LeadService(session).notes.create(
            user.tenant_id,
            lead_id,
            body=body.body,
            actor=_actor(user),
            actor_user_id=user.user_id,
        )
        return {"note": note}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/leads/{lead_id}/notes/{note_id}")
def update_note(
    lead_id: UUID,
    note_id: UUID,
    body: NoteUpdateBody,
    user: CurrentUser = Depends(_require_notes_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        note = LeadService(session).notes.update(
            user.tenant_id,
            lead_id,
            note_id,
            body=body.body,
            actor=_actor(user),
            actor_user_id=user.user_id,
        )
        return {"note": note}
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/leads/{lead_id}/notes/{note_id}")
def archive_note(
    lead_id: UUID,
    note_id: UUID,
    user: CurrentUser = Depends(_require_notes_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        note = LeadService(session).notes.archive(
            user.tenant_id,
            lead_id,
            note_id,
            actor=_actor(user),
            actor_user_id=user.user_id,
        )
        return {"note": note}
    except Exception as exc:
        raise _http(exc) from exc
