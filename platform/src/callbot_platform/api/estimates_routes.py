"""Admin Estimate CRM APIs (Phase 13)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.estimates import EstimateService
from callbot_platform.rbac.errors import RbacError

router = APIRouter(prefix="/api/admin/crm", tags=["estimates"])

_require_read = require_entitled_permission("estimates.read")
_require_create = require_entitled_permission("estimates.create")
_require_update = require_entitled_permission("estimates.update")
_require_delete = require_entitled_permission("estimates.delete")
_require_send = require_entitled_permission("estimates.send")
_require_approve = require_entitled_permission("estimates.approve")
_require_reject = require_entitled_permission("estimates.reject")
_require_convert = require_entitled_permission("estimates.convert")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, RbacError):
        return HTTPException(
            status_code=403, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, CrmError):
        status = (
            404 if exc.code == "not_found" or exc.code.endswith("_not_found") else 400
        )
        if exc.code == "forbidden":
            status = 403
        if exc.code in {
            "invalid_transition",
            "estimate_archived",
            "estimate_immutable",
            "estimate_expired",
            "estimate_not_expired",
            "estimate_conflict",
            "idempotency_conflict",
            "convert_conflict",
            "archive_not_allowed",
            "items_required",
            "unsupported_currency",
            "invalid_discount_total",
            "order_items_required",
        }:
            status = 409
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


class EstimateLineBody(BaseModel):
    model_config = {"extra": "forbid"}
    item_type: str
    service_id: UUID | None = None
    product_id: UUID | None = None
    variant_id: UUID | None = None
    pricebook_id: UUID | None = None
    name: str | None = None
    description: str | None = None
    quantity: str | int = 1
    unit_price: str | None = None
    discount_total: str | None = None
    tax_total: str | None = None
    sort_order: int | None = None


class EstimateCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    customer_id: UUID
    items: list[EstimateLineBody] = Field(min_length=1)
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    location_id: UUID | None = None
    currency: str | None = Field(default=None, max_length=3)
    estimate_discount: str | None = None
    valid_until: datetime | None = None
    notes: str | None = None
    terms: str | None = None
    pricebook_id: UUID | None = None


class EstimateUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    clear_description: bool = False
    location_id: UUID | None = None
    clear_location: bool = False
    notes: str | None = None
    clear_notes: bool = False
    terms: str | None = None
    clear_terms: bool = False
    estimate_discount: str | None = None
    valid_until: datetime | None = None
    clear_valid_until: bool = False
    items: list[EstimateLineBody] | None = None


class RejectBody(BaseModel):
    model_config = {"extra": "forbid"}
    reason: str | None = Field(default=None, max_length=2000)


class CancelBody(BaseModel):
    model_config = {"extra": "forbid"}
    reason: str | None = Field(default=None, max_length=500)


class ConvertBody(BaseModel):
    model_config = {"extra": "forbid"}
    target_type: str


def _line_dicts(items: list[EstimateLineBody]) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for item in items:
        d = item.model_dump(exclude_none=True)
        out.append(d)
    return out


@router.get("/estimates")
def list_estimates(
    q: str | None = Query(default=None),
    status: str | None = Query(default=None),
    customer_id: UUID | None = Query(default=None),  # noqa: B008
    currency: str | None = Query(default=None),
    created_from: datetime | None = Query(default=None),  # noqa: B008
    created_to: datetime | None = Query(default=None),  # noqa: B008
    valid_until_from: datetime | None = Query(default=None),  # noqa: B008
    valid_until_to: datetime | None = Query(default=None),  # noqa: B008
    total_min: str | None = Query(default=None),
    total_max: str | None = Query(default=None),
    converted: bool | None = Query(default=None),
    include_archived: bool = Query(default=False),
    limit: int | None = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        tmin = Decimal(total_min) if total_min is not None else None
        tmax = Decimal(total_max) if total_max is not None else None
    except (InvalidOperation, ValueError) as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_total", "message": "Invalid total filter"},
        ) from exc
    try:
        return EstimateService(session).list(
            user.tenant_id,
            q=q,
            status=status,
            customer_id=customer_id,
            currency=currency,
            created_from=created_from,
            created_to=created_to,
            valid_until_from=valid_until_from,
            valid_until_to=valid_until_to,
            total_min=tmin,
            total_max=tmax,
            converted=converted,
            include_archived=include_archived,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/estimates", status_code=201)
def create_estimate(
    body: EstimateCreateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        estimate = EstimateService(session).create(
            user.tenant_id,
            customer_id=body.customer_id,
            actor=_actor(user),
            items=_line_dicts(body.items),
            title=body.title,
            description=body.description,
            location_id=body.location_id,
            currency=body.currency,
            estimate_discount=body.estimate_discount,
            valid_until=body.valid_until,
            notes=body.notes,
            terms=body.terms,
            pricebook_id=body.pricebook_id,
            idempotency_key=idempotency_key,
        )
        return {"estimate": estimate}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/estimates/{estimate_id}")
def get_estimate(
    estimate_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"estimate": EstimateService(session).get(user.tenant_id, estimate_id)}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/estimates/{estimate_id}")
def update_estimate(
    estimate_id: UUID,
    body: EstimateUpdateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        estimate = EstimateService(session).update(
            user.tenant_id,
            estimate_id,
            actor=_actor(user),
            title=body.title,
            description=body.description,
            clear_description=body.clear_description,
            location_id=body.location_id,
            clear_location=body.clear_location,
            notes=body.notes,
            clear_notes=body.clear_notes,
            terms=body.terms,
            clear_terms=body.clear_terms,
            estimate_discount=body.estimate_discount,
            valid_until=body.valid_until,
            clear_valid_until=body.clear_valid_until,
            items=_line_dicts(body.items) if body.items is not None else None,
        )
        return {"estimate": estimate}
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/estimates/{estimate_id}")
def archive_estimate(
    estimate_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "estimate": EstimateService(session).archive(
                user.tenant_id, estimate_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/estimates/{estimate_id}/items")
def add_item(
    estimate_id: UUID,
    body: EstimateLineBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "estimate": EstimateService(session).add_item(
                user.tenant_id,
                estimate_id,
                actor=_actor(user),
                item=body.model_dump(exclude_none=True),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/estimates/{estimate_id}/items/{item_id}")
def remove_item(
    estimate_id: UUID,
    item_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "estimate": EstimateService(session).remove_item(
                user.tenant_id,
                estimate_id,
                item_id,
                actor=_actor(user),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/estimates/{estimate_id}/history")
def estimate_history(
    estimate_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "history": EstimateService(session).transitions.history(
                user.tenant_id, estimate_id
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/estimates/{estimate_id}/send")
def send_estimate(
    estimate_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_send),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "estimate": EstimateService(session).send(
                user.tenant_id, estimate_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/estimates/{estimate_id}/view")
def view_estimate(
    estimate_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "estimate": EstimateService(session).mark_viewed(
                user.tenant_id, estimate_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/estimates/{estimate_id}/approve")
def approve_estimate(
    estimate_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_approve),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "estimate": EstimateService(session).approve(
                user.tenant_id, estimate_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/estimates/{estimate_id}/reject")
def reject_estimate(
    estimate_id: UUID,
    body: RejectBody | None = None,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_reject),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "estimate": EstimateService(session).reject(
                user.tenant_id,
                estimate_id,
                actor=_actor(user),
                reason=(body.reason if body else None),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/estimates/{estimate_id}/cancel")
def cancel_estimate(
    estimate_id: UUID,
    body: CancelBody | None = None,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "estimate": EstimateService(session).cancel(
                user.tenant_id,
                estimate_id,
                actor=_actor(user),
                reason=(body.reason if body else None),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/estimates/{estimate_id}/convert")
def convert_estimate(
    estimate_id: UUID,
    body: ConvertBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_convert),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return EstimateService(session).convert(
            user.tenant_id,
            estimate_id,
            actor=_actor(user),
            target_type=body.target_type,
            idempotency_key=idempotency_key,
        )
    except Exception as exc:
        raise _http(exc) from exc
