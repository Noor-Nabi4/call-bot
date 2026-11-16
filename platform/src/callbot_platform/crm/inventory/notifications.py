"""Inventory alert delivery via existing notification outbox."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.inventory.constants import ALERT_OUT_OF_STOCK
from callbot_platform.crm.inventory.status import available_quantity, derive_status
from callbot_platform.db.models import Product, ProductVariant, Tenant
from callbot_platform.db.models.inventory import (
    InventoryBalance,
    InventoryItem,
    InventoryLocation,
)
from callbot_platform.scheduling.notifications import NotificationService


class InventoryNotificationService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._notifications = NotificationService(session)

    def enqueue_low_stock_email(
        self,
        *,
        tenant_id: UUID,
        item: InventoryItem,
        balance: InventoryBalance,
        alert_type: str,
        alert_event_id: UUID,
    ) -> None:
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None or not tenant.email:
            return
        variant = self._session.scalar(
            select(ProductVariant).where(
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.id == item.variant_id,
            )
        )
        product = (
            self._session.scalar(
                select(Product).where(
                    Product.tenant_id == tenant_id,
                    Product.id == variant.product_id,
                )
            )
            if variant
            else None
        )
        location = self._session.scalar(
            select(InventoryLocation).where(
                InventoryLocation.tenant_id == tenant_id,
                InventoryLocation.id == balance.location_id,
            )
        )
        business_name = tenant.name if tenant else "Organization"
        avail = available_quantity(balance.stock_quantity, balance.reserved_quantity)
        status = derive_status(
            stock=balance.stock_quantity,
            reserved=balance.reserved_quantity,
            minimum_stock=balance.minimum_stock,
        )
        label = "Low stock"
        if alert_type == ALERT_OUT_OF_STOCK:
            label = "Out of stock"
        body = (
            f"{business_name} inventory alert: {label}\n"
            f"Product: {product.name if product else ''}\n"
            f"Variant: {(variant.name if variant and variant.name else '—')}\n"
            f"SKU: {variant.sku if variant else ''}\n"
            f"Location: {location.name if location else ''}\n"
            f"Available: {avail}\n"
            f"Minimum: {balance.minimum_stock}\n"
            f"Status: {status}"
        )
        self._notifications.enqueue_email(
            tenant_id=tenant_id,
            to_address=tenant.email,
            body=body,
            idempotency_key=f"inventory-alert:{alert_event_id}:email",
        )
