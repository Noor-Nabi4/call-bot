"""Server-side estimate search and filters."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.estimates.cursors import EstimateCursor, parse_estimate_page
from callbot_platform.crm.estimates.serialize import serialize_estimate
from callbot_platform.crm.estimates.transitions import normalize_status
from callbot_platform.db.models import Customer
from callbot_platform.db.models.estimates import Estimate, EstimateItem


class EstimateSearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        tenant_id: UUID,
        *,
        q: str | None = None,
        status: str | None = None,
        customer_id: UUID | None = None,
        currency: str | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        valid_until_from: datetime | None = None,
        valid_until_to: datetime | None = None,
        total_min: Decimal | None = None,
        total_max: Decimal | None = None,
        converted: bool | None = None,
        include_archived: bool = False,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        try:
            page, decoded = parse_estimate_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        filters = [Estimate.tenant_id == tenant_id]
        if not include_archived:
            filters.append(Estimate.archived_at.is_(None))
        if status:
            filters.append(Estimate.status == normalize_status(status))
        if customer_id is not None:
            filters.append(Estimate.customer_id == customer_id)
        if currency:
            filters.append(Estimate.currency == currency.strip().upper())
        if created_from is not None:
            filters.append(Estimate.created_at >= created_from)
        if created_to is not None:
            filters.append(Estimate.created_at <= created_to)
        if valid_until_from is not None:
            filters.append(Estimate.valid_until >= valid_until_from)
        if valid_until_to is not None:
            filters.append(Estimate.valid_until <= valid_until_to)
        if total_min is not None:
            filters.append(Estimate.total >= total_min)
        if total_max is not None:
            filters.append(Estimate.total <= total_max)
        if converted is True:
            filters.append(Estimate.status == "CONVERTED")
        elif converted is False:
            filters.append(Estimate.status != "CONVERTED")

        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(Estimate.estimate_number).like(term),
                    func.lower(Estimate.title).like(term),
                    func.lower(func.coalesce(Estimate.notes, "")).like(term),
                    Estimate.customer_id.in_(
                        select(Customer.id).where(
                            Customer.tenant_id == tenant_id,
                            func.lower(Customer.name).like(term),
                        )
                    ),
                    select(EstimateItem.id)
                    .where(
                        EstimateItem.tenant_id == tenant_id,
                        EstimateItem.estimate_id == Estimate.id,
                        or_(
                            func.lower(EstimateItem.name_snapshot).like(term),
                            func.lower(
                                func.coalesce(EstimateItem.sku_snapshot, "")
                            ).like(term),
                        ),
                    )
                    .exists(),
                )
            )

        stmt = (
            select(Estimate)
            .where(and_(*filters))
            .options(
                selectinload(Estimate.customer),
                selectinload(Estimate.items),
                selectinload(Estimate.location),
            )
            .order_by(Estimate.created_at.desc(), Estimate.id.desc())
        )
        if decoded is not None:
            stmt = stmt.where(
                (Estimate.created_at < decoded.created_at)
                | (
                    (Estimate.created_at == decoded.created_at)
                    & (Estimate.id < decoded.id)
                )
            )
        rows = list(self._session.scalars(stmt.limit(page.limit + 1)).unique().all())
        next_cursor = None
        if len(rows) > page.limit:
            last = rows[page.limit - 1]
            next_cursor = EstimateCursor(
                created_at=last.created_at, id=last.id
            ).encode()
            rows = rows[: page.limit]
        return {
            "estimates": [serialize_estimate(r) for r in rows],
            "next_cursor": next_cursor,
            "limit": page.limit,
        }
