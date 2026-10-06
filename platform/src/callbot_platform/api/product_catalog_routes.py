"""Admin Product Catalog APIs (Phase 5)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.api.deps import CurrentUser, db_dep, require_entitled_permission
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.service import AuthorizationService

router = APIRouter(prefix="/api/admin/crm", tags=["product-catalog"])

_require_read = require_entitled_permission("products.read")
_require_create = require_entitled_permission("products.create")
_require_update = require_entitled_permission("products.update")
_require_delete = require_entitled_permission("products.delete")


def _http(exc: Exception) -> HTTPException:
    if isinstance(exc, CrmError):
        status = 404 if exc.code == "not_found" else 400
        if exc.code == "forbidden":
            status = 403
        if exc.code in {
            "product_archived",
            "category_in_use",
            "sku_conflict",
            "variant_conflict",
            "category_cycle",
            "image_conflict",
        }:
            status = 409
        if exc.code in {"unsupported_image_type", "object_too_large"}:
            status = 400
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    if isinstance(exc, IntegrityError):
        return HTTPException(
            status_code=409,
            detail={"code": "conflict", "message": "Conflicting catalog write"},
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": "Internal error"}
    )


def _actor(user: CurrentUser) -> str:
    return user.email or str(user.user_id)


def _include_cost(session: Session, user: CurrentUser, requested: bool) -> bool:
    if not requested:
        return False
    try:
        AuthorizationService(session).require_permission(
            user.tenant_id, user.user_id, "products.update"
        )
        return True
    except RbacError:
        return False


def _may_write_cost(session: Session, user: CurrentUser) -> bool:
    try:
        AuthorizationService(session).require_permission(
            user.tenant_id, user.user_id, "products.update"
        )
        return True
    except RbacError:
        return False


def _cost_for_write(
    session: Session,
    user: CurrentUser,
    cost: str | float | int | None,
) -> str | float | int | None:
    """Cost writes require products.update; reject when create-only callers send cost."""
    if cost is None:
        return None
    if not _may_write_cost(session, user):
        raise CrmError(
            "forbidden",
            "products.update is required to set cost",
        )
    return cost


class ProductCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=255)
    sku: str | None = Field(default=None, max_length=64)
    description: str | None = None
    category_id: UUID | None = None
    brand: str | None = Field(default=None, max_length=128)
    brand_id: UUID | None = None
    price: str | float | int | None = None
    cost: str | float | int | None = None
    tax_rate: str | float | int | None = None
    weight: str | float | int | None = None
    weight_unit: str | None = Field(default=None, max_length=8)
    status: str | None = Field(default=None, max_length=32)


class ProductUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str | None = Field(default=None, max_length=255)
    sku: str | None = Field(default=None, max_length=64)
    description: str | None = None
    category_id: UUID | None = None
    brand: str | None = Field(default=None, max_length=128)
    brand_id: UUID | None = None
    price: str | float | int | None = None
    cost: str | float | int | None = None
    tax_rate: str | float | int | None = None
    weight: str | float | int | None = None
    weight_unit: str | None = Field(default=None, max_length=8)
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
    status: str | None = Field(default=None, max_length=32)
    sort_order: int | None = None


class CategoryArchiveBody(BaseModel):
    model_config = {"extra": "forbid"}
    reassign_to_category_id: UUID | None = None
    reassign_products: bool = False


class VariantCreateBody(BaseModel):
    model_config = {"extra": "forbid"}
    sku: str = Field(min_length=1, max_length=64)
    name: str | None = Field(default=None, max_length=255)
    price: str | float | int | None = None
    cost: str | float | int | None = None
    status: str | None = Field(default=None, max_length=32)
    stock_on_hand: int | None = Field(default=None, ge=0)
    inventory_item_id: UUID | None = None
    attribute_value_ids: list[UUID] | None = None


class VariantUpdateBody(BaseModel):
    model_config = {"extra": "forbid"}
    sku: str | None = Field(default=None, max_length=64)
    name: str | None = Field(default=None, max_length=255)
    price: str | float | int | None = None
    cost: str | float | int | None = None
    status: str | None = Field(default=None, max_length=32)
    stock_on_hand: int | None = Field(default=None, ge=0)
    inventory_item_id: UUID | None = None
    attribute_value_ids: list[UUID] | None = None


# --- Products ---


@router.get("/products")
def list_products(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    q: str | None = Query(default=None, max_length=256),
    status: str | None = Query(default=None, max_length=32),
    category_id: UUID | None = Query(default=None),  # noqa: B008
    brand_id: UUID | None = Query(default=None),  # noqa: B008
    include_archived: bool = Query(default=False),
    min_price: str | None = Query(default=None),
    max_price: str | None = Query(default=None),
    has_variants: bool | None = Query(default=None),
    include_cost: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        return ProductCatalogService(session).search(
            user.tenant_id,
            q=q,
            status=status,
            category_id=category_id,
            brand_id=brand_id,
            include_archived=include_archived,
            min_price=min_price,
            max_price=max_price,
            has_variants=has_variants,
            include_cost=_include_cost(session, user, include_cost),
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/products/search")
def search_products(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    q: str = Query(min_length=1, max_length=256),
    status: str | None = Query(default=None, max_length=32),
    category_id: UUID | None = Query(default=None),  # noqa: B008
    brand_id: UUID | None = Query(default=None),  # noqa: B008
    include_archived: bool = Query(default=False),
    min_price: str | None = Query(default=None),
    max_price: str | None = Query(default=None),
    has_variants: bool | None = Query(default=None),
    include_cost: bool = Query(default=False),
    limit: int = Query(default=50, ge=1, le=200),
    cursor: str | None = Query(default=None),
) -> dict[str, Any]:
    try:
        return ProductCatalogService(session).search(
            user.tenant_id,
            q=q,
            status=status,
            category_id=category_id,
            brand_id=brand_id,
            include_archived=include_archived,
            min_price=min_price,
            max_price=max_price,
            has_variants=has_variants,
            include_cost=_include_cost(session, user, include_cost),
            limit=limit,
            cursor=cursor,
        )
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/products")
def create_product(
    body: ProductCreateBody,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_cost: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        product = ProductCatalogService(session).create(
            user.tenant_id,
            name=body.name,
            sku=body.sku,
            description=body.description,
            category_id=body.category_id,
            brand=body.brand,
            brand_id=body.brand_id,
            price=body.price,
            cost=_cost_for_write(session, user, body.cost),
            tax_rate=body.tax_rate,
            weight=body.weight,
            weight_unit=body.weight_unit,
            status=body.status,
            actor=_actor(user),
            include_cost=_include_cost(session, user, include_cost),
        )
        session.commit()
        return {"product": product}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/products/{product_id}")
def get_product(
    product_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_cost: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        product = ProductCatalogService(session).get(
            user.tenant_id,
            product_id,
            include_cost=_include_cost(session, user, include_cost),
        )
        return {"product": product}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/products/{product_id}")
def update_product(
    product_id: UUID,
    body: ProductUpdateBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_cost: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        payload = body.model_dump(exclude_unset=True)
        product = ProductCatalogService(session).update(
            user.tenant_id,
            product_id,
            actor=_actor(user),
            include_cost=_include_cost(session, user, include_cost),
            **payload,
        )
        session.commit()
        return {"product": product}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.delete("/products/{product_id}")
def archive_product(
    product_id: UUID,
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        product = ProductCatalogService(session).archive(
            user.tenant_id, product_id, actor=_actor(user)
        )
        session.commit()
        return {"product": product}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/products/{product_id}/restore")
def restore_product(
    product_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_cost: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        product = ProductCatalogService(session).restore(
            user.tenant_id,
            product_id,
            actor=_actor(user),
            include_cost=_include_cost(session, user, include_cost),
        )
        session.commit()
        return {"product": product}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


# --- Variants ---


@router.get("/products/{product_id}/variants")
def list_variants(
    product_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_archived: bool = Query(default=False),
    include_cost: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        variants = ProductCatalogService(session).variants.list(
            user.tenant_id,
            product_id,
            include_archived=include_archived,
            include_cost=_include_cost(session, user, include_cost),
        )
        return {"variants": variants}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/products/{product_id}/variants")
def create_variant(
    product_id: UUID,
    body: VariantCreateBody,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_cost: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        variant = ProductCatalogService(session).variants.create(
            user.tenant_id,
            product_id,
            sku=body.sku,
            name=body.name,
            price=body.price,
            cost=_cost_for_write(session, user, body.cost),
            status=body.status,
            stock_on_hand=body.stock_on_hand,
            inventory_item_id=body.inventory_item_id,
            attribute_value_ids=body.attribute_value_ids,
            actor=_actor(user),
            include_cost=_include_cost(session, user, include_cost),
        )
        session.commit()
        return {"variant": variant}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/products/{product_id}/variants/{variant_id}")
def get_variant(
    product_id: UUID,
    variant_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_cost: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        variant = ProductCatalogService(session).variants.get(
            user.tenant_id,
            product_id,
            variant_id,
            include_cost=_include_cost(session, user, include_cost),
        )
        return {"variant": variant}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/products/{product_id}/variants/{variant_id}")
def update_variant(
    product_id: UUID,
    variant_id: UUID,
    body: VariantUpdateBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_cost: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        payload = body.model_dump(exclude_unset=True)
        variant = ProductCatalogService(session).variants.update(
            user.tenant_id,
            product_id,
            variant_id,
            actor=_actor(user),
            include_cost=_include_cost(session, user, include_cost),
            **payload,
        )
        session.commit()
        return {"variant": variant}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.delete("/products/{product_id}/variants/{variant_id}")
def archive_variant(
    product_id: UUID,
    variant_id: UUID,
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        variant = ProductCatalogService(session).variants.archive(
            user.tenant_id, product_id, variant_id, actor=_actor(user)
        )
        session.commit()
        return {"variant": variant}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


# --- Images ---


@router.get("/products/{product_id}/images")
def list_images(
    product_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    variant_id: UUID | None = Query(default=None),  # noqa: B008
    include_archived: bool = Query(default=False),
) -> dict[str, Any]:
    try:
        images = ProductCatalogService(session).images.list(
            user.tenant_id,
            product_id,
            variant_id=variant_id,
            include_archived=include_archived,
        )
        return {"images": images}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/products/{product_id}/images")
async def upload_image(
    product_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    file: UploadFile = File(...),  # noqa: B008
    alt_text: str | None = Form(default=None),
    variant_id: UUID | None = Form(default=None),  # noqa: B008
    is_primary: bool = Form(default=False),
) -> dict[str, Any]:
    try:
        data = await file.read()
        content_type = file.content_type or "application/octet-stream"
        image = ProductCatalogService(session).images.upload(
            user.tenant_id,
            product_id,
            data=data,
            content_type=content_type,
            alt_text=alt_text,
            variant_id=variant_id,
            is_primary=is_primary,
            actor=_actor(user),
        )
        session.commit()
        return {"image": image}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/products/{product_id}/images/{image_id}/primary")
def set_primary_image(
    product_id: UUID,
    image_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        image = ProductCatalogService(session).images.set_primary(
            user.tenant_id, product_id, image_id, actor=_actor(user)
        )
        session.commit()
        return {"image": image}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.delete("/products/{product_id}/images/{image_id}")
def archive_image(
    product_id: UUID,
    image_id: UUID,
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        image = ProductCatalogService(session).images.archive(
            user.tenant_id, product_id, image_id, actor=_actor(user)
        )
        session.commit()
        return {"image": image}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


# --- Attributes ---


class AttributeBody(BaseModel):
    model_config = {"extra": "forbid"}
    name: str = Field(min_length=1, max_length=64)
    values: list[str] = Field(min_length=1)
    sort_order: int = 100


@router.post("/products/{product_id}/attributes")
def upsert_attribute(
    product_id: UUID,
    body: AttributeBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        attribute = ProductCatalogService(session).upsert_attribute(
            user.tenant_id,
            product_id,
            name=body.name,
            values=body.values,
            sort_order=body.sort_order,
            actor=_actor(user),
        )
        session.commit()
        return {"attribute": attribute}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


# --- Categories ---


@router.get("/categories")
def list_categories(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    include_archived: bool = Query(default=False),
    parent_id: UUID | None = Query(default=None),  # noqa: B008
) -> dict[str, Any]:
    try:
        categories = ProductCatalogService(session).categories.list(
            user.tenant_id,
            include_archived=include_archived,
            parent_id=parent_id,
        )
        return {"categories": categories}
    except Exception as exc:
        raise _http(exc) from exc


@router.get("/categories/tree")
def category_tree(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {"tree": ProductCatalogService(session).categories.tree(user.tenant_id)}
    except Exception as exc:
        raise _http(exc) from exc


@router.post("/categories")
def create_category(
    body: CategoryCreateBody,
    user: CurrentUser = Depends(_require_create),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        category = ProductCatalogService(session).categories.create(
            user.tenant_id,
            name=body.name,
            description=body.description,
            parent_id=body.parent_id,
            status=body.status,
            sort_order=body.sort_order,
            actor=_actor(user),
        )
        session.commit()
        return {"category": category}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.get("/categories/{category_id}")
def get_category(
    category_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        category = ProductCatalogService(session).categories.get(
            user.tenant_id, category_id
        )
        return {"category": category}
    except Exception as exc:
        raise _http(exc) from exc


@router.patch("/categories/{category_id}")
def update_category(
    category_id: UUID,
    body: CategoryUpdateBody,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        payload = body.model_dump(exclude_unset=True)
        category = ProductCatalogService(session).categories.update(
            user.tenant_id, category_id, actor=_actor(user), **payload
        )
        session.commit()
        return {"category": category}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.delete("/categories/{category_id}")
def archive_category(
    category_id: UUID,
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    body: CategoryArchiveBody | None = None,
) -> dict[str, Any]:
    try:
        payload = body or CategoryArchiveBody()
        category = ProductCatalogService(session).categories.archive(
            user.tenant_id,
            category_id,
            reassign_to_category_id=payload.reassign_to_category_id,
            reassign_products=payload.reassign_products,
            actor=_actor(user),
        )
        session.commit()
        return {"category": category}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc


@router.post("/categories/{category_id}/restore")
def restore_category(
    category_id: UUID,
    user: CurrentUser = Depends(_require_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        category = ProductCatalogService(session).categories.restore(
            user.tenant_id, category_id, actor=_actor(user)
        )
        session.commit()
        return {"category": category}
    except Exception as exc:
        session.rollback()
        raise _http(exc) from exc
