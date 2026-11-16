"""Inventory list/search queries."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from callbot_platform.crm.inventory.constants import (
    STATUS_LOW_STOCK,
    STATUS_OUT_OF_STOCK,
)
from callbot_platform.crm.inventory.serialize import serialize_balance_row
from callbot_platform.crm.inventory.status import derive_status
from callbot_platform.db.models import Product, ProductVariant
from callbot_platform.db.models.inventory import (
    InventoryBalance,
    InventoryItem,
    InventoryLocation,
)


class InventorySearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_balances(
        self,
        tenant_id: UUID,
        *,
        q: str | None = None,
        location_id: UUID | None = None,
        status: str | None = None,
        low_stock_only: bool = False,
        out_of_stock_only: bool = False,
        limit: int = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        limit = min(max(limit, 1), 200)
        stmt = (
            select(
                InventoryBalance,
                InventoryItem,
                ProductVariant,
                Product,
                InventoryLocation,
            )
            .join(
                InventoryItem,
                InventoryItem.id == InventoryBalance.inventory_item_id,
            )
            .join(
                ProductVariant,
                (ProductVariant.id == InventoryItem.variant_id)
                & (ProductVariant.tenant_id == tenant_id),
            )
            .join(
                Product,
                (Product.id == ProductVariant.product_id)
                & (Product.tenant_id == tenant_id),
            )
            .join(
                InventoryLocation,
                (InventoryLocation.id == InventoryBalance.location_id)
                & (InventoryLocation.tenant_id == tenant_id),
            )
            .where(InventoryBalance.tenant_id == tenant_id)
            .where(InventoryLocation.archived_at.is_(None))
            .where(Product.archived_at.is_(None))
            .where(ProductVariant.archived_at.is_(None))
        )
        stmt = self._apply_filters(
            stmt,
            q=q,
            location_id=location_id,
            status=status,
            low_stock_only=low_stock_only,
            out_of_stock_only=out_of_stock_only,
        )
        if cursor:
            stmt = stmt.where(InventoryBalance.id > UUID(cursor))
        stmt = stmt.order_by(InventoryBalance.updated_at.desc()).limit(limit + 1)
        rows = list(self._session.execute(stmt).all())
        next_cursor = None
        if len(rows) > limit:
            next_cursor = str(rows[limit - 1][0].id)
            rows = rows[:limit]
        items = [
            serialize_balance_row(
                balance=bal,
                item=item,
                variant=variant,
                product=product,
                location=location,
            )
            for bal, item, variant, product, location in rows
        ]
        return {"inventory": items, "next_cursor": next_cursor}

    def dashboard_summary(self, tenant_id: UUID) -> dict[str, Any]:
        balances = list(
            self._session.scalars(
                select(InventoryBalance).where(InventoryBalance.tenant_id == tenant_id)
            ).all()
        )
        item_count = self._session.scalar(
            select(func.count())
            .select_from(InventoryItem)
            .where(InventoryItem.tenant_id == tenant_id)
        )
        low = 0
        out = 0
        for bal in balances:
            st = derive_status(
                stock=bal.stock_quantity,
                reserved=bal.reserved_quantity,
                minimum_stock=bal.minimum_stock,
            )
            if st == STATUS_LOW_STOCK:
                low += 1
            elif st == STATUS_OUT_OF_STOCK:
                out += 1
        from callbot_platform.db.models.inventory import InventoryTransaction

        recent = list(
            self._session.scalars(
                select(InventoryTransaction)
                .where(InventoryTransaction.tenant_id == tenant_id)
                .order_by(InventoryTransaction.created_at.desc())
                .limit(10)
            ).all()
        )
        from callbot_platform.crm.inventory.serialize import serialize_transaction

        return {
            "total_inventory_items": int(item_count or 0),
            "low_stock_balances": low,
            "out_of_stock_balances": out,
            "recent_transactions": [serialize_transaction(t) for t in recent],
        }

    def _apply_filters(
        self,
        stmt: Select[Any],
        *,
        q: str | None,
        location_id: UUID | None,
        status: str | None,
        low_stock_only: bool,
        out_of_stock_only: bool,
    ) -> Select[Any]:
        if location_id is not None:
            stmt = stmt.where(InventoryBalance.location_id == location_id)
        if q:
            needle = f"%{q.strip().upper()}%"
            needle_lower = f"%{q.strip().lower()}%"
            stmt = stmt.where(
                or_(
                    ProductVariant.sku_normalized.like(needle),
                    func.lower(Product.name).like(needle_lower),
                    func.lower(func.coalesce(ProductVariant.name, "")).like(needle_lower),
                    InventoryLocation.code_normalized.like(needle),
                )
            )
        if status:
            stmt = self._filter_status(stmt, status.upper())
        elif low_stock_only:
            stmt = self._filter_status(stmt, STATUS_LOW_STOCK)
        elif out_of_stock_only:
            stmt = self._filter_status(stmt, STATUS_OUT_OF_STOCK)
        return stmt

    @staticmethod
    def _filter_status(stmt: Select[Any], status: str) -> Select[Any]:
        avail = InventoryBalance.stock_quantity - InventoryBalance.reserved_quantity
        if status == STATUS_OUT_OF_STOCK:
            return stmt.where(avail <= 0)
        if status == STATUS_LOW_STOCK:
            return stmt.where(avail > 0, avail <= InventoryBalance.minimum_stock)
        if status == "IN_STOCK":
            return stmt.where(avail > InventoryBalance.minimum_stock)
        return stmt
