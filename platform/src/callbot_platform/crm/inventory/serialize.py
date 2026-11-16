"""Inventory API serializers."""

from __future__ import annotations

from typing import Any

from callbot_platform.crm.inventory.status import available_quantity, derive_status
from callbot_platform.db.models import Product, ProductVariant
from callbot_platform.db.models.inventory import (
    InventoryAlertEvent,
    InventoryBalance,
    InventoryItem,
    InventoryLocation,
    InventoryTransaction,
)


def serialize_location(row: InventoryLocation) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "name": row.name,
        "code": row.code,
        "description": row.description,
        "location_type": row.location_type,
        "status": row.status,
        "is_default": row.is_default,
        "address_metadata": row.address_metadata or {},
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_at": row.created_at.isoformat(),
        "updated_at": row.updated_at.isoformat(),
    }


def serialize_balance_row(
    *,
    balance: InventoryBalance,
    item: InventoryItem,
    variant: ProductVariant,
    product: Product,
    location: InventoryLocation,
) -> dict[str, Any]:
    avail = available_quantity(balance.stock_quantity, balance.reserved_quantity)
    status = derive_status(
        stock=balance.stock_quantity,
        reserved=balance.reserved_quantity,
        minimum_stock=balance.minimum_stock,
    )
    return {
        "id": str(balance.id),
        "inventory_item_id": str(item.id),
        "location_id": str(location.id),
        "location_name": location.name,
        "location_code": location.code,
        "product_id": str(product.id),
        "product_name": product.name,
        "variant_id": str(variant.id),
        "variant_name": variant.name,
        "sku": variant.sku,
        "stock_quantity": balance.stock_quantity,
        "reserved_quantity": balance.reserved_quantity,
        "available_quantity": avail,
        "minimum_stock": balance.minimum_stock,
        "status": status,
        "updated_at": balance.updated_at.isoformat(),
    }


def serialize_item_detail(
    *,
    item: InventoryItem,
    variant: ProductVariant,
    product: Product,
    balances: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "id": str(item.id),
        "variant_id": str(variant.id),
        "product_id": str(product.id),
        "product_name": product.name,
        "variant_name": variant.name,
        "sku": variant.sku,
        "balances": balances,
    }


def serialize_transaction(row: InventoryTransaction) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "inventory_item_id": str(row.inventory_item_id),
        "location_id": str(row.location_id),
        "transaction_type": row.transaction_type,
        "quantity": row.quantity,
        "stock_before": row.stock_before,
        "stock_after": row.stock_after,
        "reserved_before": row.reserved_before,
        "reserved_after": row.reserved_after,
        "reference_type": row.reference_type,
        "reference_id": row.reference_id,
        "reason": row.reason,
        "metadata": row.metadata_json or {},
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat(),
        "idempotency_key": row.idempotency_key,
    }


def serialize_alert_event(row: InventoryAlertEvent) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "inventory_item_id": str(row.inventory_item_id),
        "location_id": str(row.location_id),
        "alert_type": row.alert_type,
        "previous_status": row.previous_status,
        "current_status": row.current_status,
        "available_quantity": row.available_quantity,
        "minimum_stock": row.minimum_stock,
        "email_notification_status": row.email_notification_status,
        "sms_notification_status": row.sms_notification_status,
        "created_at": row.created_at.isoformat(),
    }
