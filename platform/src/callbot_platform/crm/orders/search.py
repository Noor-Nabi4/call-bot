"""Server-side order search and filters."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.orders.cursors import OrderCursor, parse_order_page
from callbot_platform.crm.orders.serialize import serialize_order
from callbot_platform.crm.orders.transitions import normalize_status
from callbot_platform.db.models import Customer
from callbot_platform.db.models.orders import Order, OrderItem


class OrderSearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        tenant_id: UUID,
        *,
        q: str | None = None,
        status: str | None = None,
        customer_id: UUID | None = None,
        product_id: UUID | None = None,
        sku: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        include_archived: bool = False,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        try:
            page, decoded = parse_order_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        filters = [Order.tenant_id == tenant_id]
        if not include_archived:
            filters.append(Order.archived_at.is_(None))
        if status:
            filters.append(Order.status == normalize_status(status))
        if customer_id is not None:
            filters.append(Order.customer_id == customer_id)
        if created_from is not None:
            filters.append(Order.created_at >= created_from)
        if created_to is not None:
            filters.append(Order.created_at <= created_to)

        if product_id is not None or (sku and sku.strip()):
            item_filters = [
                OrderItem.tenant_id == tenant_id,
                OrderItem.order_id == Order.id,
            ]
            if product_id is not None:
                item_filters.append(OrderItem.product_id == product_id)
            if sku and sku.strip():
                item_filters.append(
                    func.lower(OrderItem.sku_snapshot) == sku.strip().lower()
                )
            filters.append(select(OrderItem.id).where(*item_filters).exists())

        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(Order.order_number).like(term),
                    func.lower(func.coalesce(Order.notes, "")).like(term),
                    Order.customer_id.in_(
                        select(Customer.id).where(
                            Customer.tenant_id == tenant_id,
                            func.lower(Customer.name).like(term),
                        )
                    ),
                    select(OrderItem.id)
                    .where(
                        OrderItem.tenant_id == tenant_id,
                        OrderItem.order_id == Order.id,
                        or_(
                            func.lower(OrderItem.sku_snapshot).like(term),
                            func.lower(OrderItem.product_name_snapshot).like(term),
                        ),
                    )
                    .exists(),
                )
            )

        stmt = (
            select(Order)
            .where(and_(*filters))
            .options(selectinload(Order.customer), selectinload(Order.items))
            .order_by(Order.created_at.desc(), Order.id.desc())
        )
        if decoded is not None:
            stmt = stmt.where(
                or_(
                    Order.created_at < decoded.created_at,
                    and_(
                        Order.created_at == decoded.created_at,
                        Order.id < decoded.id,
                    ),
                )
            )
        stmt = stmt.limit(page.limit + 1)
        rows = list(self._session.scalars(stmt).all())
        next_cursor = None
        if len(rows) > page.limit:
            last = rows[page.limit - 1]
            next_cursor = OrderCursor(created_at=last.created_at, id=last.id).encode()
            rows = rows[: page.limit]

        return {
            "orders": [serialize_order(r) for r in rows],
            "next_cursor": next_cursor,
            "limit": page.limit,
        }
