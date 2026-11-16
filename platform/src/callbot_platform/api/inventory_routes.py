"""Admin Inventory APIs (Phase 6)."""

# ruff: noqa: B008

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.inventory import InventoryService

router = APIRouter(prefix="/api/admin/crm/inventory", tags=["inventory"])

_require_read = require_entitled_permission("inventory.read")
_require_create = require_entitled_permission("inventory.create")
_require_adjust = require_entitled_permission("inventory.adjust")
_require_reserve = require_entitled_permission("inventory.reserve")
_require_release = require_entitled_permission("inventory.release")
_require_configure = require_entitled_permission("inventory.configure")
_require_delete = require_entitled_permission("inventory.delete")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, CrmError):
        status = 404 if exc.code == "not_found" else 400
        if exc.code in {
            "location_has_stock",
            "location_has_reservations",
            "insufficient_stock",
            "insufficient_available",
            "insufficient_reserved",
        }:
            status = 409
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


class LocationCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=255)
    code: str = Field(min_length=1, max_length=64)
    description: str | None = None
    location_type: str = "OTHER"
    status: str = "ACTIVE"
    is_default: bool = False
    address_metadata: dict[str, Any] | None = None


class LocationUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    description: str | None = None
    location_type: str | None = None
    status: str | None = None
    is_default: bool | None = None
    address_metadata: dict[str, Any] | None = None


class MutationBody(BaseModel):
    model_config = {"extra": "forbid"}
    location_id: UUID
    quantity: int
    reason: str | None = None
    reference_type: str | None = Field(default=None, max_length=64)
    reference_id: str | None = Field(default=None, max_length=128)
    metadata: dict[str, Any] | None = None


class MinimumStockBody(BaseModel):
    model_config = {"extra": "forbid"}
    location_id: UUID
    minimum_stock: int = Field(ge=0)


@router.get("/dashboard")
def inventory_dashboard(
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_read),
) -> dict[str, Any]:
    try:
        return InventoryService(session).dashboard(user.tenant_id)
    except CrmError as exc:
        raise _http(exc) from exc


@router.get("/locations")
def list_locations(
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_read),
    status: str | None = None,
    include_archived: bool = False,
    limit: int = Query(default=100, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, Any]:
    return InventoryService(session).locations.list(
        user.tenant_id,
        status=status,
        include_archived=include_archived,
        limit=limit,
        cursor=cursor,
    )


@router.post("/locations")
def create_location(
    body: LocationCreateBody,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_create),
) -> dict[str, Any]:
    try:
        return InventoryService(session).locations.create(
            user.tenant_id,
            name=body.name,
            code=body.code,
            description=body.description,
            location_type=body.location_type,
            status=body.status,
            is_default=body.is_default,
            address_metadata=body.address_metadata,
            actor=_actor(user),
        )
    except CrmError as exc:
        raise _http(exc) from exc


@router.get("/locations/{location_id}")
def get_location(
    location_id: UUID,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_read),
) -> dict[str, Any]:
    try:
        return InventoryService(session).locations.get(user.tenant_id, location_id)
    except CrmError as exc:
        raise _http(exc) from exc


@router.patch("/locations/{location_id}")
def update_location(
    location_id: UUID,
    body: LocationUpdateBody,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_configure),
) -> dict[str, Any]:
    try:
        fields = body.model_dump(exclude_unset=True)
        return InventoryService(session).locations.update(
            user.tenant_id, location_id, actor=_actor(user), fields=fields
        )
    except CrmError as exc:
        raise _http(exc) from exc


@router.delete("/locations/{location_id}")
def archive_location(
    location_id: UUID,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_delete),
) -> dict[str, Any]:
    try:
        return InventoryService(session).locations.archive(
            user.tenant_id, location_id, actor=_actor(user)
        )
    except CrmError as exc:
        raise _http(exc) from exc


@router.post("/locations/{location_id}/restore")
def restore_location(
    location_id: UUID,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_create),
) -> dict[str, Any]:
    try:
        return InventoryService(session).locations.restore(
            user.tenant_id, location_id, actor=_actor(user)
        )
    except CrmError as exc:
        raise _http(exc) from exc


@router.get("")
def list_inventory(
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_read),
    q: str | None = None,
    location_id: UUID | None = None,
    status: str | None = None,
    low_stock: bool = False,
    out_of_stock: bool = False,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, Any]:
    return InventoryService(session).list_inventory(
        user.tenant_id,
        q=q,
        location_id=location_id,
        status=status,
        low_stock_only=low_stock,
        out_of_stock_only=out_of_stock,
        limit=limit,
        cursor=cursor,
    )


@router.get("/{inventory_item_id}")
def get_inventory_item(
    inventory_item_id: UUID,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_read),
) -> dict[str, Any]:
    try:
        return InventoryService(session).get_item(user.tenant_id, inventory_item_id)
    except CrmError as exc:
        raise _http(exc) from exc


@router.get("/{inventory_item_id}/transactions")
def list_transactions(
    inventory_item_id: UUID,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_read),
    location_id: UUID | None = None,
    transaction_type: str | None = None,
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = None,
) -> dict[str, Any]:
    try:
        return InventoryService(session).list_transactions(
            user.tenant_id,
            inventory_item_id,
            location_id=location_id,
            transaction_type=transaction_type,
            limit=limit,
            cursor=cursor,
        )
    except CrmError as exc:
        raise _http(exc) from exc


def _mutation(
    session: Session,
    user: CurrentUser,
    inventory_item_id: UUID,
    body: MutationBody,
    *,
    method: str,
    idempotency_key: str | None,
) -> dict[str, Any]:
    svc = InventoryService(session).mutations
    common = {
        "location_id": body.location_id,
        "quantity": body.quantity,
        "actor": _actor(user),
        "reason": body.reason,
        "reference_type": body.reference_type,
        "reference_id": body.reference_id,
        "idempotency_key": idempotency_key,
        "metadata": body.metadata,
    }
    if method == "purchase":
        return svc.purchase(user.tenant_id, inventory_item_id, **common)
    if method == "sale":
        return svc.sale(user.tenant_id, inventory_item_id, **common)
    if method == "adjust":
        if not body.reason:
            raise CrmError("reason_required", "Adjustment requires a reason")
        return svc.adjust(user.tenant_id, inventory_item_id, **common)
    if method == "return":
        return svc.return_stock(user.tenant_id, inventory_item_id, **common)
    if method == "reserve":
        return svc.reserve(user.tenant_id, inventory_item_id, **common)
    if method == "release":
        return svc.release(user.tenant_id, inventory_item_id, **common)
    raise CrmError("invalid_method", "Unknown mutation")


@router.post("/{inventory_item_id}/purchase")
def purchase(
    inventory_item_id: UUID,
    body: MutationBody,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_adjust),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return _mutation(
            session, user, inventory_item_id, body, method="purchase", idempotency_key=idempotency_key
        )
    except CrmError as exc:
        raise _http(exc) from exc


@router.post("/{inventory_item_id}/sale")
def sale(
    inventory_item_id: UUID,
    body: MutationBody,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_adjust),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return _mutation(
            session, user, inventory_item_id, body, method="sale", idempotency_key=idempotency_key
        )
    except CrmError as exc:
        raise _http(exc) from exc


@router.post("/{inventory_item_id}/adjust")
def adjust(
    inventory_item_id: UUID,
    body: MutationBody,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_adjust),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return _mutation(
            session, user, inventory_item_id, body, method="adjust", idempotency_key=idempotency_key
        )
    except CrmError as exc:
        raise _http(exc) from exc


@router.post("/{inventory_item_id}/return")
def return_stock(
    inventory_item_id: UUID,
    body: MutationBody,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_adjust),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return _mutation(
            session, user, inventory_item_id, body, method="return", idempotency_key=idempotency_key
        )
    except CrmError as exc:
        raise _http(exc) from exc


@router.post("/{inventory_item_id}/reserve")
def reserve(
    inventory_item_id: UUID,
    body: MutationBody,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_reserve),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return _mutation(
            session, user, inventory_item_id, body, method="reserve", idempotency_key=idempotency_key
        )
    except CrmError as exc:
        raise _http(exc) from exc


@router.post("/{inventory_item_id}/release")
def release(
    inventory_item_id: UUID,
    body: MutationBody,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_release),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> dict[str, Any]:
    try:
        return _mutation(
            session, user, inventory_item_id, body, method="release", idempotency_key=idempotency_key
        )
    except CrmError as exc:
        raise _http(exc) from exc


@router.patch("/{inventory_item_id}/minimum-stock")
def set_minimum_stock(
    inventory_item_id: UUID,
    body: MinimumStockBody,
    session: Session = Depends(db_dep),
    user: CurrentUser = Depends(_require_configure),
) -> dict[str, Any]:
    try:
        return InventoryService(session).set_minimum_stock(
            user.tenant_id,
            inventory_item_id,
            location_id=body.location_id,
            minimum_stock=body.minimum_stock,
            actor=_actor(user),
        )
    except CrmError as exc:
        raise _http(exc) from exc
