"""Server-side service search with cursor pagination."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.services.cursors import ServiceCursor, parse_service_page
from callbot_platform.crm.services.normalize import (
    escape_like,
    normalize_status,
    parse_money,
)
from callbot_platform.crm.services.serialize import serialize_service
from callbot_platform.db.models.services import Service, ServiceCategory


class ServiceSearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        tenant_id: UUID,
        *,
        q: str | None = None,
        status: str | None = None,
        category_id: UUID | None = None,
        include_archived: bool = False,
        min_price: object | None = None,
        max_price: object | None = None,
        min_duration: int | None = None,
        max_duration: int | None = None,
        include_cost: bool = True,
        limit: int | None = None,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        try:
            page, decoded = parse_service_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        stmt = select(Service).where(Service.tenant_id == tenant_id)
        if not include_archived:
            stmt = stmt.where(Service.archived_at.is_(None))
        if status is not None and status.strip():
            stmt = stmt.where(Service.status == normalize_status(status))
        if category_id is not None:
            stmt = stmt.where(Service.category_id == category_id)

        min_p = parse_money(min_price, field="min_price")
        max_p = parse_money(max_price, field="max_price")
        if min_p is not None:
            stmt = stmt.where(Service.base_price >= min_p)
        if max_p is not None:
            stmt = stmt.where(Service.base_price <= max_p)
        if min_duration is not None:
            if min_duration <= 0:
                raise CrmError("invalid_min_duration", "min_duration must be positive")
            stmt = stmt.where(Service.duration_minutes >= min_duration)
        if max_duration is not None:
            if max_duration <= 0:
                raise CrmError("invalid_max_duration", "max_duration must be positive")
            stmt = stmt.where(Service.duration_minutes <= max_duration)

        term = (q or "").strip()
        if term:
            like = f"{escape_like(term)}%"
            like_contains = f"%{escape_like(term)}%"
            term_upper = term.upper()
            cat_ids = list(
                self._session.scalars(
                    select(ServiceCategory.id).where(
                        ServiceCategory.tenant_id == tenant_id,
                        ServiceCategory.archived_at.is_(None),
                        ServiceCategory.name.ilike(like_contains, escape="\\"),
                    )
                ).all()
            )
            clauses = [
                Service.name.ilike(like_contains, escape="\\"),
                Service.description.ilike(like_contains, escape="\\"),
                Service.code_normalized.like(f"{escape_like(term_upper)}%"),
                Service.code.ilike(like, escape="\\"),
            ]
            if cat_ids:
                clauses.append(Service.category_id.in_(cat_ids))
            stmt = stmt.where(or_(*clauses))

        if decoded is not None:
            stmt = stmt.where(
                or_(
                    Service.updated_at < decoded.updated_at,
                    and_(
                        Service.updated_at == decoded.updated_at,
                        Service.id < decoded.id,
                    ),
                )
            )

        stmt = stmt.order_by(Service.updated_at.desc(), Service.id.desc()).limit(
            page.limit + 1
        )
        rows = list(self._session.scalars(stmt).all())
        has_more = len(rows) > page.limit
        rows = rows[: page.limit]

        category_ids = {r.category_id for r in rows if r.category_id}
        names: dict[UUID, str] = {}
        if category_ids:
            for cid, cname in self._session.execute(
                select(ServiceCategory.id, ServiceCategory.name).where(
                    ServiceCategory.tenant_id == tenant_id,
                    ServiceCategory.id.in_(category_ids),
                )
            ).all():
                names[cid] = cname

        items = [
            serialize_service(
                row,
                category_name=names.get(row.category_id) if row.category_id else None,
                include_cost=include_cost,
            )
            for row in rows
        ]
        next_cursor = None
        if has_more and rows:
            last = rows[-1]
            next_cursor = ServiceCursor(updated_at=last.updated_at, id=last.id).encode()
        return {"services": items, "next_cursor": next_cursor}
