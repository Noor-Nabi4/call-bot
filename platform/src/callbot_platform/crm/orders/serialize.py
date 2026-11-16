"""Order serialization."""

from __future__ import annotations

from typing import Any

from callbot_platform.crm.orders.money import serialize_money
from callbot_platform.db.models import Customer
from callbot_platform.db.models.orders import Order, OrderItem, OrderStatusHistory


def serialize_order_item(item: OrderItem) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "tenant_id": str(item.tenant_id),
        "order_id": str(item.order_id),
        "product_id": str(item.product_id),
        "variant_id": str(item.variant_id) if item.variant_id else None,
        "sku_snapshot": item.sku_snapshot,
        "product_name_snapshot": item.product_name_snapshot,
        "variant_name_snapshot": item.variant_name_snapshot,
        "unit_price": serialize_money(item.unit_price),
        "quantity": item.quantity,
        "discount_total": serialize_money(item.discount_total),
        "tax_total": serialize_money(item.tax_total),
        "line_subtotal": serialize_money(item.line_subtotal),
        "line_total": serialize_money(item.line_total),
        "sort_order": item.sort_order,
        "created_at": item.created_at.isoformat() if item.created_at else None,
    }


def serialize_status_history(row: OrderStatusHistory) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "order_id": str(row.order_id),
        "from_status": row.from_status,
        "to_status": row.to_status,
        "changed_by": row.changed_by,
        "reason": row.reason,
        "metadata": row.metadata_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_order(
    order: Order,
    *,
    customer: Customer | None = None,
    include_items: bool = True,
    include_history: bool = False,
) -> dict[str, Any]:
    cust = customer if customer is not None else getattr(order, "customer", None)
    items = (
        sorted(order.items or [], key=lambda i: (i.sort_order, str(i.id)))
        if include_items
        else []
    )
    payload: dict[str, Any] = {
        "id": str(order.id),
        "tenant_id": str(order.tenant_id),
        "order_number": order.order_number,
        "customer_id": str(order.customer_id),
        "customer": (
            {
                "id": str(cust.id),
                "display_name": cust.name,
                "name": cust.name,
                "status": cust.status,
            }
            if cust is not None
            else None
        ),
        "status": order.status,
        "currency": order.currency,
        "subtotal": serialize_money(order.subtotal),
        "discount_total": serialize_money(order.discount_total),
        "tax_total": serialize_money(order.tax_total),
        "shipping_total": serialize_money(order.shipping_total),
        "total": serialize_money(order.total),
        "notes": order.notes,
        "shipping_address_snapshot": order.shipping_address_snapshot,
        "billing_address_snapshot": order.billing_address_snapshot,
        "fulfillment_location_id": (
            str(order.fulfillment_location_id)
            if order.fulfillment_location_id
            else None
        ),
        "inventory_reserved": order.inventory_reserved,
        "inventory_consumed": order.inventory_consumed,
        "idempotency_key": order.idempotency_key,
        "archived_at": order.archived_at.isoformat() if order.archived_at else None,
        "created_by": order.created_by,
        "updated_by": order.updated_by,
        "created_at": order.created_at.isoformat() if order.created_at else None,
        "updated_at": order.updated_at.isoformat() if order.updated_at else None,
    }
    if include_items:
        payload["items"] = [serialize_order_item(i) for i in items]
    if include_history:
        history = sorted(
            order.status_history or [],
            key=lambda h: (
                h.created_at.isoformat() if h.created_at else "",
                str(h.id),
            ),
        )
        payload["status_history"] = [serialize_status_history(h) for h in history]
    return payload
