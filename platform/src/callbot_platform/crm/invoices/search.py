"""Server-side invoice search and filters."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.invoices.constants import PAYMENT_ELIGIBLE_STATUSES
from callbot_platform.crm.invoices.cursors import InvoiceCursor, parse_invoice_page
from callbot_platform.crm.invoices.serialize import serialize_invoice
from callbot_platform.crm.invoices.transitions import normalize_status
from callbot_platform.db.models import Customer
from callbot_platform.db.models.invoices import Invoice


class InvoiceSearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        tenant_id: UUID,
        *,
        q: str | None = None,
        status: str | None = None,
        customer_id: UUID | None = None,
        job_id: UUID | None = None,
        order_id: UUID | None = None,
        overdue_only: bool = False,
        due_from: datetime | None = None,
        due_to: datetime | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        try:
            page, decoded = parse_invoice_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        filters = [Invoice.tenant_id == tenant_id]
        if status:
            filters.append(Invoice.status == normalize_status(status))
        if customer_id is not None:
            filters.append(Invoice.customer_id == customer_id)
        if job_id is not None:
            filters.append(Invoice.job_id == job_id)
        if order_id is not None:
            filters.append(Invoice.order_id == order_id)
        if due_from is not None:
            filters.append(Invoice.due_date >= due_from)
        if due_to is not None:
            filters.append(Invoice.due_date <= due_to)
        if created_from is not None:
            filters.append(Invoice.created_at >= created_from)
        if created_to is not None:
            filters.append(Invoice.created_at <= created_to)
        if overdue_only:
            now = datetime.now(UTC)
            filters.append(
                and_(
                    Invoice.status.in_(tuple(PAYMENT_ELIGIBLE_STATUSES)),
                    Invoice.due_date < now,
                    Invoice.balance_due > 0,
                )
            )

        stmt = select(Invoice).where(*filters).options(selectinload(Invoice.customer))
        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            stmt = stmt.join(Customer, Customer.id == Invoice.customer_id).where(
                or_(
                    func.lower(Invoice.invoice_number).like(term),
                    func.lower(Invoice.notes).like(term),
                    func.lower(Customer.name).like(term),
                )
            )

        stmt = (
            stmt.order_by(Invoice.created_at.desc(), Invoice.id.desc()).limit(
                page.limit + 1
            )
        )
        if decoded is not None:
            stmt = stmt.where(
                or_(
                    Invoice.created_at < decoded.created_at,
                    and_(
                        Invoice.created_at == decoded.created_at,
                        Invoice.id < decoded.id,
                    ),
                )
            )

        rows = list(self._session.scalars(stmt).all())
        has_more = len(rows) > page.limit
        if has_more:
            rows = rows[: page.limit]
        next_cursor = (
            InvoiceCursor(created_at=rows[-1].created_at, id=rows[-1].id).encode()
            if has_more and rows
            else None
        )
        return {
            "invoices": [serialize_invoice(r) for r in rows],
            "next_cursor": next_cursor,
        }
