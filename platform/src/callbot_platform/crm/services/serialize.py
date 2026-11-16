"""Serialization for services & pricebook domain."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from callbot_platform.crm.services.normalize import money_to_str
from callbot_platform.db.models.services import (
    Pricebook,
    PricebookItem,
    PricebookItemComponent,
    PricebookOverride,
    Service,
    ServiceCategory,
)


def serialize_category(
    cat: ServiceCategory, *, service_count: int | None = None
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(cat.id),
        "name": cat.name,
        "slug": cat.slug,
        "description": cat.description,
        "parent_id": str(cat.parent_id) if cat.parent_id else None,
        "status": cat.status,
        "sort_order": cat.sort_order,
        "archived_at": cat.archived_at.isoformat() if cat.archived_at else None,
        "created_at": cat.created_at.isoformat() if cat.created_at else None,
        "updated_at": cat.updated_at.isoformat() if cat.updated_at else None,
    }
    if service_count is not None:
        payload["service_count"] = service_count
    return payload


def serialize_service(
    row: Service,
    *,
    category_name: str | None = None,
    include_cost: bool = True,
) -> dict[str, Any]:
    payload: dict[str, Any] = {
        "id": str(row.id),
        "name": row.name,
        "code": row.code,
        "description": row.description,
        "category_id": str(row.category_id) if row.category_id else None,
        "category_name": category_name,
        "duration_minutes": row.duration_minutes,
        "base_price": money_to_str(row.base_price),
        "tax_rate": money_to_str(row.tax_rate),
        "pricing_type": row.pricing_type,
        "status": row.status,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if include_cost:
        payload["cost"] = money_to_str(row.cost)
    return payload


def serialize_pricebook(row: Pricebook) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "name": row.name,
        "description": row.description,
        "status": row.status,
        "is_default": row.is_default,
        "effective_from": (
            row.effective_from.isoformat() if row.effective_from else None
        ),
        "effective_until": (
            row.effective_until.isoformat() if row.effective_until else None
        ),
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_component(
    row: PricebookItemComponent,
    *,
    variant_sku: str | None = None,
    variant_name: str | None = None,
) -> dict[str, Any]:
    qty = row.quantity
    unit = row.unit_price
    total: Decimal | None = None
    if unit is not None:
        total = qty * unit
    return {
        "id": str(row.id),
        "component_type": row.component_type,
        "name": row.name,
        "product_variant_id": (
            str(row.product_variant_id) if row.product_variant_id else None
        ),
        "variant_sku": variant_sku,
        "variant_name": variant_name,
        "quantity": money_to_str(qty),
        "unit_price": money_to_str(unit),
        "line_total": money_to_str(total),
        "sort_order": row.sort_order,
    }


def serialize_item(
    row: PricebookItem,
    *,
    service_name: str | None = None,
    service_code: str | None = None,
    components: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "pricebook_id": str(row.pricebook_id),
        "service_id": str(row.service_id),
        "service_name": service_name,
        "service_code": service_code,
        "pricing_type": row.pricing_type,
        "price": money_to_str(row.price),
        "starting_price": money_to_str(row.starting_price),
        "hourly_rate": money_to_str(row.hourly_rate),
        "effective_from": (
            row.effective_from.isoformat() if row.effective_from else None
        ),
        "effective_until": (
            row.effective_until.isoformat() if row.effective_until else None
        ),
        "status": row.status,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        "components": components or [],
    }


def serialize_override(row: PricebookOverride) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "pricebook_id": str(row.pricebook_id),
        "service_id": str(row.service_id),
        "override_price": money_to_str(row.override_price),
        "pricing_type": row.pricing_type,
        "effective_from": (
            row.effective_from.isoformat() if row.effective_from else None
        ),
        "effective_until": (
            row.effective_until.isoformat() if row.effective_until else None
        ),
        "status": row.status,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
