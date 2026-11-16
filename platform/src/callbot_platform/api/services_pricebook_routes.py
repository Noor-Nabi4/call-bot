"""Admin Services & Pricebook APIs (Phase 7)."""

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
from callbot_platform.crm.services import ServicesPricebookService

router = APIRouter(prefix="/api/admin/crm", tags=["services-pricebook"])

_require_services_read = require_entitled_permission("services.read")
_require_services_create = require_entitled_permission("services.create")
_require_services_update = require_entitled_permission("services.update")
_require_services_delete = require_entitled_permission("services.delete")

_require_cat_read = require_entitled_permission("service_categories.read")
_require_cat_create = require_entitled_permission("service_categories.create")
_require_cat_update = require_entitled_permission("service_categories.update")
_require_cat_delete = require_entitled_permission("service_categories.delete")

_require_pb_read = require_entitled_permission("pricebooks.read")
_require_pb_create = require_entitled_permission("pricebooks.create")
_require_pb_update = require_entitled_permission("pricebooks.update")
_require_pb_delete = require_entitled_permission("pricebooks.delete")

_require_pbi_read = require_entitled_permission("pricebook_items.read")
_require_pbi_create = require_entitled_permission("pricebook_items.create")
_require_pbi_update = require_entitled_permission("pricebook_items.update")
_require_pbi_delete = require_entitled_permission("pricebook_items.delete")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, CrmError):
        status = 404 if exc.code == "not_found" else 400
        if exc.code == "forbidden":
            status = 403
        if exc.code in {
            "code_conflict",
            "name_conflict",
            "category_cycle",
            "category_in_use",
            "category_has_children",
            "default_conflict",
            "effective_overlap",
            "service_archived",
            "category_archived",
            "pricebook_archived",
            "item_archived",
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


# --- Bodies ---


class ServiceCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    description: str | None = None
    category_id: UUID | None = None
    duration_minutes: int | None = Field(default=None, gt=0)
    base_price: str | float | int | None = None
    cost: str | float | int | None = None
    tax_rate: str | float | int | None = None
    pricing_type: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=32)


class ServiceUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, max_length=255)
    code: str | None = Field(default=None, max_length=64)
    clear_code: bool = False
    description: str | None = None
    category_id: UUID | None = None
    clear_category: bool = False
    duration_minutes: int | None = Field(default=None, gt=0)
    clear_duration: bool = False
    base_price: str | float | int | None = None
    clear_base_price: bool = False
    cost: str | float | int | None = None
    clear_cost: bool = False
    tax_rate: str | float | int | None = None
    clear_tax_rate: bool = False
    pricing_type: str | None = Field(default=None, max_length=32)
    status: str | None = Field(default=None, max_length=32)


class CategoryCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    parent_id: UUID | None = None
    status: str | None = Field(default=None, max_length=32)
    sort_order: int | None = None


class CategoryUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    parent_id: UUID | None = None
    clear_parent: bool = False
    status: str | None = Field(default=None, max_length=32)
    sort_order: int | None = None


class CategoryArchiveBody(BaseModel):
    model_config = {"extra": "forbid"}
    reassign_to_category_id: UUID | None = None
    reassign_services: bool = False


class PricebookCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=128)
    description: str | None = None
    status: str | None = Field(default=None, max_length=32)
    is_default: bool = False
    effective_from: datetime | None = None
    effective_until: datetime | None = None


class PricebookUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, max_length=128)
    description: str | None = None
    status: str | None = Field(default=None, max_length=32)
    is_default: bool | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    clear_effective: bool = False


class ComponentBody(BaseModel):
    model_config = {"extra": "forbid"}
    component_type: str = Field(min_length=1, max_length=32)
    name: str | None = Field(default=None, max_length=255)
    product_variant_id: UUID | None = None
    quantity: str | float | int | None = "1"
    unit_price: str | float | int | None = None
    sort_order: int | None = None


class PricebookItemCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    service_id: UUID
    pricing_type: str = Field(min_length=1, max_length=32)
    price: str | float | int | None = None
    starting_price: str | float | int | None = None
    hourly_rate: str | float | int | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    status: str | None = Field(default=None, max_length=32)
    components: list[ComponentBody] | None = None


class PricebookItemUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    pricing_type: str | None = Field(default=None, max_length=32)
    price: str | float | int | None = None
    starting_price: str | float | int | None = None
    hourly_rate: str | float | int | None = None
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    clear_effective: bool = False
    status: str | None = Field(default=None, max_length=32)
    components: list[ComponentBody] | None = None


class OverrideCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    service_id: UUID
    override_price: str | float | int | None = None
    pricing_type: str | None = Field(default=None, max_length=32)
    effective_from: datetime | None = None
    effective_until: datetime | None = None
    status: str | None = Field(default=None, max_length=32)


# --- Services ---


@router.get("/services")
def list_services(
    user: CurrentUser = Depends(_require_services_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    q: str | None = Query(default=None, max_length=256),
    status: str | None = Query(default=None, max_length=32),
    category_id: UUID | None = Query(default=None),  # noqa: B008
    include_archived: bool = Query(default=False),
    min_price: str | None = Query(default=None),
    max_price: str | None = Query(default=None),
    min_duration: int | None = Query(default=None, gt=0),
    max_duration: int | None = Query(default=None, gt=0),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).list_services(
            user.tenant_id,
            q=q,
            status=status,
            category_id=category_id,
            include_archived=include_archived,
            min_price=min_price,
            max_price=max_price,
            min_duration=min_duration,
            max_duration=max_duration,
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/services", status_code=201)
def create_service(
    body: ServiceCreateBody,
    user: CurrentUser = Depends(_require_services_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).create_service(
            user.tenant_id,
            name=body.name,
            code=body.code,
            description=body.description,
            category_id=body.category_id,
            duration_minutes=body.duration_minutes,
            base_price=body.base_price,
            cost=body.cost,
            tax_rate=body.tax_rate,
            pricing_type=body.pricing_type,
            status=body.status,
            actor=_actor(user),
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/services/{service_id}")
def get_service(
    service_id: UUID,
    user: CurrentUser = Depends(_require_services_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_archived: bool = Query(default=True),
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).get_service(
            user.tenant_id,
            service_id,
            include_archived=include_archived,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/services/{service_id}")
def update_service(
    service_id: UUID,
    body: ServiceUpdateBody,
    user: CurrentUser = Depends(_require_services_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).update_service(
            user.tenant_id,
            service_id,
            name=body.name,
            code=body.code,
            clear_code=body.clear_code,
            description=body.description,
            category_id=body.category_id,
            clear_category=body.clear_category,
            duration_minutes=body.duration_minutes,
            clear_duration=body.clear_duration,
            base_price=body.base_price,
            clear_base_price=body.clear_base_price,
            cost=body.cost,
            clear_cost=body.clear_cost,
            tax_rate=body.tax_rate,
            clear_tax_rate=body.clear_tax_rate,
            pricing_type=body.pricing_type,
            status=body.status,
            actor=_actor(user),
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/services/{service_id}")
def archive_service(
    service_id: UUID,
    user: CurrentUser = Depends(_require_services_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).archive_service(
            user.tenant_id, service_id, actor=_actor(user)
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/services/{service_id}/restore")
def restore_service(
    service_id: UUID,
    user: CurrentUser = Depends(_require_services_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).restore_service(
            user.tenant_id, service_id, actor=_actor(user)
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/services/{service_id}/pricing")
def resolve_service_pricing(
    service_id: UUID,
    user: CurrentUser = Depends(_require_services_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    pricebook_id: UUID | None = Query(default=None),  # noqa: B008
    at: datetime | None = Query(default=None),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).resolve_price(
            user.tenant_id,
            service_id=service_id,
            pricebook_id=pricebook_id,
            at=at,
        )
    except Exception as exc:
        raise _http(exc) from exc


# --- Categories ---


@router.get("/service-categories")
def list_service_categories(
    user: CurrentUser = Depends(_require_cat_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_archived: bool = Query(default=False),
    parent_id: UUID | None = Query(default=None),  # noqa: B008
) -> dict[str, Any]:
    try:
        rows = ServicesPricebookService(session).categories.list(
            user.tenant_id,
            include_archived=include_archived,
            parent_id=parent_id,
        )
        return {"categories": rows}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/service-categories/tree")
def service_category_tree(
    user: CurrentUser = Depends(_require_cat_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "tree": ServicesPricebookService(session).categories.tree(user.tenant_id)
        }
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/service-categories", status_code=201)
def create_service_category(
    body: CategoryCreateBody,
    user: CurrentUser = Depends(_require_cat_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).categories.create(
            user.tenant_id,
            name=body.name,
            description=body.description,
            parent_id=body.parent_id,
            status=body.status,
            sort_order=body.sort_order,
            actor=_actor(user),
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/service-categories/{category_id}")
def get_service_category(
    category_id: UUID,
    user: CurrentUser = Depends(_require_cat_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).categories.get(
            user.tenant_id, category_id
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/service-categories/{category_id}")
def update_service_category(
    category_id: UUID,
    body: CategoryUpdateBody,
    user: CurrentUser = Depends(_require_cat_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).categories.update(
            user.tenant_id,
            category_id,
            name=body.name,
            description=body.description,
            parent_id=body.parent_id,
            clear_parent=body.clear_parent,
            status=body.status,
            sort_order=body.sort_order,
            actor=_actor(user),
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/service-categories/{category_id}")
def archive_service_category(
    category_id: UUID,
    body: CategoryArchiveBody | None = None,
    user: CurrentUser = Depends(_require_cat_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    payload = body or CategoryArchiveBody()
    try:
        return ServicesPricebookService(session).categories.archive(
            user.tenant_id,
            category_id,
            reassign_to_category_id=payload.reassign_to_category_id,
            reassign_services=payload.reassign_services,
            actor=_actor(user),
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/service-categories/{category_id}/restore")
def restore_service_category(
    category_id: UUID,
    user: CurrentUser = Depends(_require_cat_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).categories.restore(
            user.tenant_id, category_id, actor=_actor(user)
        )
    except Exception as exc:
        raise _http(exc) from exc


# --- Pricebooks ---


@router.get("/pricebooks")
def list_pricebooks(
    user: CurrentUser = Depends(_require_pb_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_archived: bool = Query(default=False),
    status: str | None = Query(default=None, max_length=32),
) -> dict[str, Any]:
    try:
        rows = ServicesPricebookService(session).pricebooks.list(
            user.tenant_id,
            include_archived=include_archived,
            status=status,
        )
        return {"pricebooks": rows}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/pricebooks", status_code=201)
def create_pricebook(
    body: PricebookCreateBody,
    user: CurrentUser = Depends(_require_pb_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).pricebooks.create(
            user.tenant_id,
            name=body.name,
            description=body.description,
            status=body.status,
            is_default=body.is_default,
            effective_from=body.effective_from,
            effective_until=body.effective_until,
            actor=_actor(user),
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/pricebooks/{pricebook_id}")
def get_pricebook(
    pricebook_id: UUID,
    user: CurrentUser = Depends(_require_pb_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).pricebooks.get(
            user.tenant_id, pricebook_id
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/pricebooks/{pricebook_id}")
def update_pricebook(
    pricebook_id: UUID,
    body: PricebookUpdateBody,
    user: CurrentUser = Depends(_require_pb_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).pricebooks.update(
            user.tenant_id,
            pricebook_id,
            name=body.name,
            description=body.description,
            status=body.status,
            is_default=body.is_default,
            effective_from=body.effective_from,
            effective_until=body.effective_until,
            clear_effective=body.clear_effective,
            actor=_actor(user),
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/pricebooks/{pricebook_id}")
def archive_pricebook(
    pricebook_id: UUID,
    user: CurrentUser = Depends(_require_pb_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).pricebooks.archive(
            user.tenant_id, pricebook_id, actor=_actor(user)
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/pricebooks/{pricebook_id}/restore")
def restore_pricebook(
    pricebook_id: UUID,
    user: CurrentUser = Depends(_require_pb_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).pricebooks.restore(
            user.tenant_id, pricebook_id, actor=_actor(user)
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/pricebooks/{pricebook_id}/items")
def list_pricebook_items(
    pricebook_id: UUID,
    user: CurrentUser = Depends(_require_pbi_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_archived: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        rows = ServicesPricebookService(session).pricebooks.list_items(
            user.tenant_id,
            pricebook_id,
            include_archived=include_archived,
        )
        return {"items": rows}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/pricebooks/{pricebook_id}/items", status_code=201)
def create_pricebook_item(
    pricebook_id: UUID,
    body: PricebookItemCreateBody,
    user: CurrentUser = Depends(_require_pbi_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        comps = [c.model_dump() for c in (body.components or [])]
        return ServicesPricebookService(session).pricebooks.create_item(
            user.tenant_id,
            pricebook_id,
            service_id=body.service_id,
            pricing_type=body.pricing_type,
            price=body.price,
            starting_price=body.starting_price,
            hourly_rate=body.hourly_rate,
            effective_from=body.effective_from,
            effective_until=body.effective_until,
            status=body.status,
            components=comps,
            actor=_actor(user),
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/pricebooks/{pricebook_id}/items/{item_id}")
def update_pricebook_item(
    pricebook_id: UUID,
    item_id: UUID,
    body: PricebookItemUpdateBody,
    user: CurrentUser = Depends(_require_pbi_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        comps = (
            [c.model_dump() for c in body.components]
            if body.components is not None
            else None
        )
        return ServicesPricebookService(session).pricebooks.update_item(
            user.tenant_id,
            pricebook_id,
            item_id,
            pricing_type=body.pricing_type,
            price=body.price,
            starting_price=body.starting_price,
            hourly_rate=body.hourly_rate,
            effective_from=body.effective_from,
            effective_until=body.effective_until,
            clear_effective=body.clear_effective,
            status=body.status,
            components=comps,
            actor=_actor(user),
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/pricebooks/{pricebook_id}/items/{item_id}")
def archive_pricebook_item(
    pricebook_id: UUID,
    item_id: UUID,
    user: CurrentUser = Depends(_require_pbi_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).pricebooks.archive_item(
            user.tenant_id, pricebook_id, item_id, actor=_actor(user)
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/pricebooks/{pricebook_id}/overrides", status_code=201)
def create_pricebook_override(
    pricebook_id: UUID,
    body: OverrideCreateBody,
    user: CurrentUser = Depends(_require_pb_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).pricebooks.create_override(
            user.tenant_id,
            pricebook_id,
            service_id=body.service_id,
            override_price=body.override_price,
            pricing_type=body.pricing_type,
            effective_from=body.effective_from,
            effective_until=body.effective_until,
            status=body.status,
            actor=_actor(user),
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.delete("/pricebooks/{pricebook_id}/overrides/{override_id}")
def archive_pricebook_override(
    pricebook_id: UUID,
    override_id: UUID,
    user: CurrentUser = Depends(_require_pb_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return ServicesPricebookService(session).pricebooks.archive_override(
            user.tenant_id, pricebook_id, override_id, actor=_actor(user)
        )
    except Exception as exc:
        raise _http(exc) from exc
