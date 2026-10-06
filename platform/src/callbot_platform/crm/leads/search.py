"""Server-side lead search, filters, and pipeline aggregation."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.leads.constants import PIPELINE_ORDER
from callbot_platform.crm.leads.cursors import LeadCursor, parse_lead_page
from callbot_platform.crm.leads.normalize import (
    normalize_priority,
    normalize_source,
    normalize_status,
)
from callbot_platform.crm.leads.serialize import serialize_lead
from callbot_platform.db.models import Customer, Lead
from callbot_platform.db.models.catalog.product import Product
from callbot_platform.db.models.jobs import TenantUser
from callbot_platform.db.models.services.service import Service


class LeadSearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        tenant_id: UUID,
        *,
        q: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        source: str | None = None,
        owner_user_id: UUID | None = None,
        customer_id: UUID | None = None,
        service_id: UUID | None = None,
        product_id: UUID | None = None,
        created_from: datetime | None = None,
        created_to: datetime | None = None,
        updated_from: datetime | None = None,
        updated_to: datetime | None = None,
        include_archived: bool = False,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        try:
            page, decoded = parse_lead_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        filters = [Lead.tenant_id == tenant_id]
        if not include_archived:
            filters.append(Lead.archived_at.is_(None))
        if status:
            filters.append(Lead.status == normalize_status(status))
        if priority:
            filters.append(Lead.priority == normalize_priority(priority))
        if source:
            filters.append(Lead.source == normalize_source(source))
        if owner_user_id is not None:
            filters.append(Lead.owner_user_id == owner_user_id)
        if customer_id is not None:
            filters.append(Lead.customer_id == customer_id)
        if service_id is not None:
            filters.append(Lead.service_id == service_id)
        if product_id is not None:
            filters.append(Lead.product_id == product_id)
        if created_from is not None:
            filters.append(Lead.created_at >= created_from)
        if created_to is not None:
            filters.append(Lead.created_at <= created_to)
        if updated_from is not None:
            filters.append(Lead.updated_at >= updated_from)
        if updated_to is not None:
            filters.append(Lead.updated_at <= updated_to)

        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(Lead.title).like(term),
                    func.lower(Lead.service_type).like(term),
                    func.lower(func.coalesce(Lead.description, "")).like(term),
                    func.lower(func.coalesce(Lead.reference_code, "")).like(term),
                    func.lower(func.coalesce(Lead.prospect_name, "")).like(term),
                    func.lower(func.coalesce(Lead.prospect_email, "")).like(term),
                    func.lower(func.coalesce(Lead.prospect_phone, "")).like(term),
                    Lead.customer_id.in_(
                        select(Customer.id).where(
                            Customer.tenant_id == tenant_id,
                            func.lower(Customer.name).like(term),
                        )
                    ),
                )
            )

        if decoded is not None:
            filters.append(
                or_(
                    Lead.created_at < decoded.created_at,
                    and_(
                        Lead.created_at == decoded.created_at,
                        Lead.id < decoded.id,
                    ),
                )
            )

        stmt = (
            select(Lead)
            .where(*filters)
            .options(selectinload(Lead.customer), selectinload(Lead.conversion))
            .order_by(Lead.created_at.desc(), Lead.id.desc())
            .limit(page.limit + 1)
        )
        rows = list(self._session.scalars(stmt).all())
        next_cursor = None
        if len(rows) > page.limit:
            rows = rows[: page.limit]
            last = rows[-1]
            next_cursor = LeadCursor(created_at=last.created_at, id=last.id).encode()

        # Batch-load related display rows to avoid N+1.
        service_ids = {r.service_id for r in rows if r.service_id}
        product_ids = {r.product_id for r in rows if r.product_id}
        owner_ids = {r.owner_user_id for r in rows if r.owner_user_id}
        services = {
            s.id: s
            for s in self._session.scalars(
                select(Service).where(
                    Service.tenant_id == tenant_id, Service.id.in_(service_ids)
                )
            ).all()
            if service_ids
        }
        products = {
            p.id: p
            for p in self._session.scalars(
                select(Product).where(
                    Product.tenant_id == tenant_id, Product.id.in_(product_ids)
                )
            ).all()
            if product_ids
        }
        owners = {
            u.id: u
            for u in self._session.scalars(
                select(TenantUser).where(
                    TenantUser.tenant_id == tenant_id, TenantUser.id.in_(owner_ids)
                )
            ).all()
            if owner_ids
        }

        return {
            "leads": [
                serialize_lead(
                    r,
                    service=services.get(r.service_id) if r.service_id else None,
                    product=products.get(r.product_id) if r.product_id else None,
                    owner=owners.get(r.owner_user_id) if r.owner_user_id else None,
                )
                for r in rows
            ],
            "next_cursor": next_cursor,
            "limit": page.limit,
        }

    def pipeline_counts(
        self,
        tenant_id: UUID,
        *,
        owner_user_id: UUID | None = None,
        source: str | None = None,
        priority: str | None = None,
        include_archived: bool = False,
    ) -> dict[str, Any]:
        filters = [Lead.tenant_id == tenant_id]
        if not include_archived:
            filters.append(Lead.archived_at.is_(None))
        if owner_user_id is not None:
            filters.append(Lead.owner_user_id == owner_user_id)
        if source:
            filters.append(Lead.source == normalize_source(source))
        if priority:
            filters.append(Lead.priority == normalize_priority(priority))

        rows = self._session.execute(
            select(Lead.status, func.count()).where(*filters).group_by(Lead.status)
        ).all()
        counts = dict.fromkeys(PIPELINE_ORDER, 0)
        total = 0
        for status, count in rows:
            key = str(status).upper()
            if key in counts:
                counts[key] = int(count)
            total += int(count)
        return {
            "counts": counts,
            "total": total,
            "statuses": list(PIPELINE_ORDER),
        }
