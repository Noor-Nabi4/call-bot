"""Inventory items linked to product variants."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.products.constants import SKU_OWNER_VARIANT
from callbot_platform.db.models import CatalogSku, ProductVariant
from callbot_platform.db.models.inventory import InventoryItem


class InventoryItemService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_row(self, tenant_id: UUID, item_id: UUID) -> InventoryItem:
        row = self._session.scalar(
            select(InventoryItem).where(
                InventoryItem.tenant_id == tenant_id,
                InventoryItem.id == item_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Inventory item not found")
        return row

    def ensure_for_variant(
        self,
        tenant_id: UUID,
        variant_id: UUID,
        *,
        actor: str,
    ) -> InventoryItem:
        existing = self._session.scalar(
            select(InventoryItem).where(
                InventoryItem.tenant_id == tenant_id,
                InventoryItem.variant_id == variant_id,
            )
        )
        if existing is not None:
            return existing

        variant = self._session.scalar(
            select(ProductVariant).where(
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.id == variant_id,
            )
        )
        if variant is None:
            raise CrmError("not_found", "Product variant not found")
        if variant.archived_at is not None:
            raise CrmError("variant_archived", "Variant is archived")

        sku_row = self._session.scalar(
            select(CatalogSku).where(
                CatalogSku.tenant_id == tenant_id,
                CatalogSku.owner_kind == SKU_OWNER_VARIANT,
                CatalogSku.owner_id == variant_id,
            )
        )
        item = InventoryItem(
            tenant_id=tenant_id,
            variant_id=variant_id,
            sku_id=sku_row.id if sku_row else None,
        )
        try:
            with self._session.begin_nested():
                self._session.add(item)
                self._session.flush()
        except IntegrityError:
            raced = self._session.scalar(
                select(InventoryItem).where(
                    InventoryItem.tenant_id == tenant_id,
                    InventoryItem.variant_id == variant_id,
                )
            )
            if raced is None:
                raise CrmError(
                    "inventory_item_conflict",
                    "Could not create inventory item for variant",
                ) from None
            return raced
        variant.inventory_item_id = item.id
        _ = actor
        return item

    def get_by_variant(self, tenant_id: UUID, variant_id: UUID) -> InventoryItem | None:
        return self._session.scalar(
            select(InventoryItem).where(
                InventoryItem.tenant_id == tenant_id,
                InventoryItem.variant_id == variant_id,
            )
        )

    def backfill_missing_for_tenant(
        self, tenant_id: UUID, *, actor: str = "backfill"
    ) -> dict[str, Any]:
        """Idempotent: ensure every active variant has an inventory item."""
        variants = list(
            self._session.scalars(
                select(ProductVariant).where(
                    ProductVariant.tenant_id == tenant_id,
                    ProductVariant.archived_at.is_(None),
                )
            ).all()
        )
        before = 0
        created = 0
        already_existing = 0
        failed = 0
        for variant in variants:
            existing = self.get_by_variant(tenant_id, variant.id)
            if existing is not None:
                already_existing += 1
                if variant.inventory_item_id is None:
                    variant.inventory_item_id = existing.id
                continue
            before += 1
            try:
                self.ensure_for_variant(tenant_id, variant.id, actor=actor)
                created += 1
            except CrmError:
                failed += 1
        self._session.flush()
        return {
            "tenant_id": str(tenant_id),
            "variants_without_inventory_item_before": before,
            "created": created,
            "already_existing": already_existing,
            "failed": failed,
        }

    def load_variant_context(
        self, tenant_id: UUID, item_id: UUID
    ) -> tuple[InventoryItem, ProductVariant]:
        item = self.get_row(tenant_id, item_id)
        variant = self._session.scalar(
            select(ProductVariant).where(
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.id == item.variant_id,
            )
        )
        if variant is None:
            raise CrmError("not_found", "Product variant not found")
        return item, variant
