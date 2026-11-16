"""Admin Order CRM APIs (Phase 9)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.orders import OrderService
from callbot_platform.crm.orders.constants import OrderStatus
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.service import AuthorizationService

router = APIRouter(prefix="/api/admin/crm", tags=["orders"])

_require_read = require_entitled_permission("orders.read")
_require_create = require_entitled_permission("orders.create")
_require_update = require_entitled_permission("orders.update")
_require_delete = require_entitled_permission("orders.delete")
_require_transition = require_entitled_permission("orders.transition")
_require_cancel = require_entitled_permission("orders.cancel")
_require_refund = require_entitled_permission("orders.refund")


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
        if exc.code.endswith("_not_found"):
            status = 404
        if exc.code in {
            "invalid_transition",
            "order_archived",
            "order_immutable",
            "use_transition",
            "archive_not_allowed",
            "order_conflict",
            "insufficient_stock",
            "insufficient_available",
            "insufficient_reserved",
            "product_archived",
            "product_inactive",
            "variant_archived",
            "variant_inactive",
            "variant_product_mismatch",
            "unsupported_currency",
            "items_required",
            "idempotency_conflict",
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


class OrderLineBody(BaseModel):
    model_config = {"extra": "forbid"}
    product_id: UUID
    variant_id: UUID | None = None
    quantity: int = Field(ge=1)
    unit_price: str | None = None
    discount_total: str | None = None
    tax_total: str | None = None
    sort_order: int | None = None


class OrderCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    customer_id: UUID
    items: list[OrderLineBody] = Field(min_length=1)
    currency: str | None = Field(default=None, max_length=3)
    notes: str | None = None
    shipping_total: str | None = None
    order_discount: str | None = None
    shipping_address_snapshot: dict[str, Any] | None = None
    billing_address_snapshot: dict[str, Any] | None = None
    fulfillment_location_id: UUID | None = None
    idempotency_key: str | None = Field(default=None, max_length=128)


class OrderUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    notes: str | None = None
    clear_notes: bool = False
    shipping_total: str | None = None
    order_discount: str | None = None
    shipping_address_snapshot: dict[str, Any] | None = None
    billing_address_snapshot: dict[str, Any] | None = None
    fulfillment_location_id: UUID | None = None
    clear_fulfillment_location: bool = False
    items: list[OrderLineBody] | None = None
    status: str | None = Field(default=None, max_length=32)


class TransitionBody(BaseModel):
    model_config = {"extra": "forbid"}
    to_status: str = Field(min_length=1, max_length=32)
    reason: str | None = Field(default=None, max_length=500)


class ReasonBody(BaseModel):
    model_config = {"extra": "forbid"}
    reason: str | None = Field(default=None, max_length=500)


@router.get("/orders")
def list_orders(
    q: str | None = None,
    status: str | None = None,
    customer_id: UUID | None = None,
    product_id: UUID | None = None,
    sku: str | None = None,
    created_from: datetime | None = None,
    created_to: datetime | None = None,
    include_archived: bool = False,
    limit: int | None = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return OrderService(session).list(
            user.tenant_id,
            q=q,
            status=status,
            customer_id=customer_id,
            product_id=product_id,
            sku=sku,
            created_from=created_from,
            created_to=created_to,
            include_archived=include_archived,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/orders", status_code=201)
def create_order(
    body: OrderCreateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        order = OrderService(session).create(
            user.tenant_id,
            customer_id=body.customer_id,
            actor=_actor(user),
            items=[item.model_dump() for item in body.items],
            currency=body.currency,
            notes=body.notes,
            shipping_total=body.shipping_total,
            order_discount=body.order_discount,
            shipping_address_snapshot=body.shipping_address_snapshot,
            billing_address_snapshot=body.billing_address_snapshot,
            fulfillment_location_id=body.fulfillment_location_id,
            idempotency_key=idempotency_key or body.idempotency_key,
        )
        return {"order": order}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/orders/{order_id}")
def get_order(
    order_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"order": OrderService(session).get(user.tenant_id, order_id)}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/orders/{order_id}")
def update_order(
    order_id: UUID,
    body: OrderUpdateBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        order = OrderService(session).update(
            user.tenant_id,
            order_id,
            actor=_actor(user),
            notes=body.notes,
            clear_notes=body.clear_notes,
            shipping_total=body.shipping_total,
            order_discount=body.order_discount,
            shipping_address_snapshot=body.shipping_address_snapshot,
            billing_address_snapshot=body.billing_address_snapshot,
            fulfillment_location_id=body.fulfillment_location_id,
            clear_fulfillment_location=body.clear_fulfillment_location,
            items=(
                [item.model_dump() for item in body.items]
                if body.items is not None
                else None
            ),
            status=body.status,
        )
        return {"order": order}
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/orders/{order_id}")
def archive_order(
    order_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "order": OrderService(session).archive(
                user.tenant_id, order_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/orders/{order_id}/restore")
def restore_order(
    order_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_update),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "order": OrderService(session).restore(
                user.tenant_id, order_id, actor=_actor(user)
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/orders/{order_id}/transition")
def transition_order(
    order_id: UUID,
    body: TransitionBody,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_transition),  # noqa: B008
) -> dict[str, Any]:
    target = body.to_status.strip().upper()
    # Cancel/refund require elevated permissions even via the transition endpoint.
    if target == OrderStatus.CANCELLED.value:
        try:
            AuthorizationService(session).require_permission(
                user.tenant_id, user.user_id, "orders.cancel"
            )
        except RbacError as exc:
            raise _http(exc) from exc
    if target == OrderStatus.REFUNDED.value:
        try:
            AuthorizationService(session).require_permission(
                user.tenant_id, user.user_id, "orders.refund"
            )
        except RbacError as exc:
            raise _http(exc) from exc
    try:
        return {
            "order": OrderService(session).transition(
                user.tenant_id,
                order_id,
                to_status=body.to_status,
                actor=_actor(user),
                reason=body.reason,
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/orders/{order_id}/cancel")
def cancel_order(
    order_id: UUID,
    body: ReasonBody | None = None,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_cancel),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "order": OrderService(session).transition(
                user.tenant_id,
                order_id,
                to_status=OrderStatus.CANCELLED.value,
                actor=_actor(user),
                reason=(body.reason if body else None),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/orders/{order_id}/refund")
def refund_order(
    order_id: UUID,
    body: ReasonBody | None = None,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_refund),  # noqa: B008
) -> dict[str, Any]:
    """Mark order REFUNDED (lifecycle only — no payment provider call)."""
    try:
        return {
            "order": OrderService(session).transition(
                user.tenant_id,
                order_id,
                to_status=OrderStatus.REFUNDED.value,
                actor=_actor(user),
                reason=(body.reason if body else None),
            )
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/orders/{order_id}/history")
def order_history(
    order_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    user: CurrentUser = Depends(_require_read),  # noqa: B008
) -> dict[str, Any]:
    try:
        return OrderService(session).history(user.tenant_id, order_id)
    except Exception as exc:
        raise _http(exc) from exc
