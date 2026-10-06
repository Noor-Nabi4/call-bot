"""Estimate serialization."""

from __future__ import annotations

from typing import Any

from callbot_platform.crm.estimates.money import serialize_money
from callbot_platform.db.models.estimates import (
    Estimate,
    EstimateConversion,
    EstimateItem,
    EstimateStatusHistory,
)


def serialize_item(item: EstimateItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "item_type": item.item_type,
        "service_id": str(item.service_id) if item.service_id else None,
        "product_id": str(item.product_id) if item.product_id else None,
        "variant_id": str(item.variant_id) if item.variant_id else None,
        "pricebook_id": str(item.pricebook_id) if item.pricebook_id else None,
        "name_snapshot": item.name_snapshot,
        "description_snapshot": item.description_snapshot,
        "sku_snapshot": item.sku_snapshot,
        "code_snapshot": item.code_snapshot,
        "pricing_source_snapshot": item.pricing_source_snapshot,
        "tax_rate_snapshot": (
            serialize_money(item.tax_rate_snapshot)
            if item.tax_rate_snapshot is not None
            else None
        ),
        "quantity": serialize_money(item.quantity),
        "unit_price": serialize_money(item.unit_price),
        "discount_total": serialize_money(item.discount_total),
        "tax_total": serialize_money(item.tax_total),
        "line_subtotal": serialize_money(item.line_subtotal),
        "line_total": serialize_money(item.line_total),
        "sort_order": item.sort_order,
        "created_at": item.created_at.isoformat() if item.created_at else None,
        "updated_at": item.updated_at.isoformat() if item.updated_at else None,
    }


def serialize_status_history(row: EstimateStatusHistory) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "from_status": row.from_status,
        "to_status": row.to_status,
        "changed_by": row.changed_by,
        "reason": row.reason,
        "metadata": row.metadata_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_conversion(row: EstimateConversion) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "estimate_id": str(row.estimate_id),
        "target_type": row.target_type,
        "target_id": str(row.target_id),
        "target_number": row.target_number,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_estimate(
    estimate: Estimate,
    *,
    include_history: bool = False,
    include_conversions: bool = False,
) -> dict[str, Any]:
    customer = None
    if estimate.customer is not None:
        customer = {
            "id": str(estimate.customer.id),
            "name": estimate.customer.name,
            "display_name": estimate.customer.name,
            "email": estimate.customer.email,
            "status": getattr(estimate.customer, "status", None),
        }
    location = None
    if estimate.location is not None:
        location = {
            "id": str(estimate.location.id),
            "label": estimate.location.label,
            "address_line_1": estimate.location.address_line_1,
            "city": estimate.location.city,
            "state": estimate.location.state,
            "postal_code": estimate.location.postal_code,
        }
    items = sorted(estimate.items or [], key=lambda i: (i.sort_order, str(i.id)))
    payload: dict[str, Any] = {
        "id": str(estimate.id),
        "tenant_id": str(estimate.tenant_id),
        "estimate_number": estimate.estimate_number,
        "customer_id": str(estimate.customer_id),
        "customer": customer,
        "location_id": str(estimate.location_id) if estimate.location_id else None,
        "location": location,
        "title": estimate.title,
        "description": estimate.description,
        "status": estimate.status,
        "currency": estimate.currency,
        "subtotal": serialize_money(estimate.subtotal),
        "discount_total": serialize_money(estimate.discount_total),
        "tax_total": serialize_money(estimate.tax_total),
        "total": serialize_money(estimate.total),
        "estimate_discount": serialize_money(estimate.estimate_discount),
        "valid_until": (
            estimate.valid_until.isoformat() if estimate.valid_until else None
        ),
        "notes": estimate.notes,
        "terms": estimate.terms,
        "pricebook_id": str(estimate.pricebook_id) if estimate.pricebook_id else None,
        "approved_at": (
            estimate.approved_at.isoformat() if estimate.approved_at else None
        ),
        "approved_by": estimate.approved_by,
        "rejected_at": (
            estimate.rejected_at.isoformat() if estimate.rejected_at else None
        ),
        "rejected_by": estimate.rejected_by,
        "rejection_reason": estimate.rejection_reason,
        "converted_at": (
            estimate.converted_at.isoformat() if estimate.converted_at else None
        ),
        "archived_at": (
            estimate.archived_at.isoformat() if estimate.archived_at else None
        ),
        "created_by": estimate.created_by,
        "updated_by": estimate.updated_by,
        "created_at": estimate.created_at.isoformat() if estimate.created_at else None,
        "updated_at": estimate.updated_at.isoformat() if estimate.updated_at else None,
        "items": [serialize_item(i) for i in items],
    }
    if include_history:
        hist = sorted(
            estimate.status_history or [],
            key=lambda h: (h.created_at or estimate.created_at, str(h.id)),
        )
        payload["status_history"] = [serialize_status_history(h) for h in hist]
    if include_conversions:
        convs = sorted(
            estimate.conversions or [],
            key=lambda c: (c.created_at or estimate.created_at, str(c.id)),
        )
        payload["conversions"] = [serialize_conversion(c) for c in convs]
    return payload
