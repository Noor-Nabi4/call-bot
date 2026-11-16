"""Inventory application service facade."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.inventory.items import InventoryItemService
from callbot_platform.crm.inventory.locations import InventoryLocationService
from callbot_platform.crm.inventory.mutations import InventoryMutationService
from callbot_platform.crm.inventory.search import InventorySearchService
from callbot_platform.crm.inventory.serialize import (
    serialize_balance_row,
    serialize_item_detail,
    serialize_transaction,
)
from callbot_platform.crm.inventory.status import available_quantity, derive_status
from callbot_platform.db.models import Product, ProductVariant
from callbot_platform.db.models.inventory import InventoryBalance, InventoryLocation


class InventoryService:
    """Tenant-scoped inventory operations (authorization at route layer)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.locations = InventoryLocationService(session)
        self.items = InventoryItemService(session)
        self.mutations = InventoryMutationService(session)
        self._search = InventorySearchService(session)

    def list_inventory(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self._search.list_balances(tenant_id, **kwargs)

    def dashboard(self, tenant_id: UUID) -> dict[str, Any]:
        return self._search.dashboard_summary(tenant_id)

    def get_item(self, tenant_id: UUID, inventory_item_id: UUID) -> dict[str, Any]:
        item, variant = self.items.load_variant_context(tenant_id, inventory_item_id)
        product = self._session.scalar(
            select(Product).where(
                Product.tenant_id == tenant_id,
                Product.id == variant.product_id,
            )
        )
        if product is None:
            raise CrmError("not_found", "Product not found")
        balances = list(
            self._session.scalars(
                select(InventoryBalance).where(
                    InventoryBalance.tenant_id == tenant_id,
                    InventoryBalance.inventory_item_id == item.id,
                )
            ).all()
        )
        loc_ids = [b.location_id for b in balances]
        locations = {
            loc.id: loc
            for loc in self._session.scalars(
                select(InventoryLocation).where(
                    InventoryLocation.tenant_id == tenant_id,
                    InventoryLocation.id.in_(loc_ids),
                )
            ).all()
        }
        serialized_balances = [
            serialize_balance_row(
                balance=bal,
                item=item,
                variant=variant,
                product=product,
                location=locations[bal.location_id],
            )
            for bal in balances
            if bal.location_id in locations
        ]
        return serialize_item_detail(
            item=item,
            variant=variant,
            product=product,
            balances=serialized_balances,
        )

    def list_transactions(
        self,
        tenant_id: UUID,
        inventory_item_id: UUID,
        *,
        location_id: UUID | None = None,
        transaction_type: str | None = None,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        self.items.get_row(tenant_id, inventory_item_id)
        from callbot_platform.db.models.inventory import InventoryTransaction

        limit = min(max(limit, 1), 200)
        stmt = select(InventoryTransaction).where(
            InventoryTransaction.tenant_id == tenant_id,
            InventoryTransaction.inventory_item_id == inventory_item_id,
        )
        if location_id is not None:
            stmt = stmt.where(InventoryTransaction.location_id == location_id)
        if transaction_type:
            stmt = stmt.where(
                InventoryTransaction.transaction_type == transaction_type.upper()
            )
        if cursor:
            stmt = stmt.where(InventoryTransaction.id < UUID(cursor))
        stmt = stmt.order_by(InventoryTransaction.created_at.desc()).limit(limit + 1)
        rows = list(self._session.scalars(stmt).all())
        next_cursor = None
        if len(rows) > limit:
            next_cursor = str(rows[limit - 1].id)
            rows = rows[:limit]
        return {
            "transactions": [serialize_transaction(r) for r in rows],
            "next_cursor": next_cursor,
        }

    def set_minimum_stock(
        self,
        tenant_id: UUID,
        inventory_item_id: UUID,
        *,
        location_id: UUID,
        minimum_stock: int,
        actor: str,
    ) -> dict[str, Any]:
        if minimum_stock < 0:
            raise CrmError("invalid_minimum", "minimum_stock must be non-negative")
        self.items.get_row(tenant_id, inventory_item_id)
        self.locations.get_row(tenant_id, location_id)
        balance = self.mutations.configure_minimum(
            tenant_id,
            inventory_item_id,
            location_id=location_id,
            minimum_stock=minimum_stock,
        )
        _ = actor
        item, variant = self.items.load_variant_context(tenant_id, inventory_item_id)
        product = self._session.scalar(
            select(Product).where(
                Product.tenant_id == tenant_id,
                Product.id == variant.product_id,
            )
        )
        location = self.locations.get_row(tenant_id, location_id)
        assert product is not None
        return serialize_balance_row(
            balance=balance,
            item=item,
            variant=variant,
            product=product,
            location=location,
        )

    def ensure_item_for_variant(
        self, tenant_id: UUID, variant_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        item = self.items.ensure_for_variant(tenant_id, variant_id, actor=actor)
        return {"inventory_item_id": str(item.id)}

    def get_inventory_by_sku(
        self, tenant_id: UUID, sku: str, *, location_id: UUID | None = None
    ) -> dict[str, Any]:
        # Catalog stores sku_normalized as uppercase (see products.normalize_sku).
        needle = sku.strip().upper()
        variant = self._session.scalar(
            select(ProductVariant).where(
                ProductVariant.tenant_id == tenant_id,
                ProductVariant.sku_normalized == needle,
                ProductVariant.archived_at.is_(None),
            )
        )
        if variant is None:
            raise CrmError("not_found", "SKU not found")
        item = self.items.ensure_for_variant(tenant_id, variant.id, actor="system")
        detail = self.get_item(tenant_id, item.id)
        if location_id is not None:
            detail["balances"] = [
                b for b in detail["balances"] if b["location_id"] == str(location_id)
            ]
        return detail

    def check_available_quantity(
        self,
        tenant_id: UUID,
        *,
        inventory_item_id: UUID,
        location_id: UUID,
    ) -> dict[str, Any]:
        balance = self._session.scalar(
            select(InventoryBalance).where(
                InventoryBalance.tenant_id == tenant_id,
                InventoryBalance.inventory_item_id == inventory_item_id,
                InventoryBalance.location_id == location_id,
            )
        )
        if balance is None:
            return {
                "available_quantity": 0,
                "stock_quantity": 0,
                "reserved_quantity": 0,
                "status": "OUT_OF_STOCK",
            }
        avail = available_quantity(balance.stock_quantity, balance.reserved_quantity)
        return {
            "available_quantity": avail,
            "stock_quantity": balance.stock_quantity,
            "reserved_quantity": balance.reserved_quantity,
            "status": derive_status(
                stock=balance.stock_quantity,
                reserved=balance.reserved_quantity,
                minimum_stock=balance.minimum_stock,
            ),
        }
