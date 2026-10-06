"""Server-side job search and filters."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs.constants import normalize_priority, normalize_status
from callbot_platform.crm.jobs.cursors import JobCursor, parse_job_page
from callbot_platform.crm.jobs.serialize import serialize_job
from callbot_platform.db.models import Customer
from callbot_platform.db.models.jobs import Job


class JobSearchService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def search(
        self,
        tenant_id: UUID,
        *,
        q: str | None = None,
        status: str | None = None,
        priority: str | None = None,
        customer_id: UUID | None = None,
        technician_id: UUID | None = None,
        service_id: UUID | None = None,
        location_id: UUID | None = None,
        scheduled_from: datetime | None = None,
        scheduled_to: datetime | None = None,
        include_archived: bool = False,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        try:
            page, decoded = parse_job_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        filters = [Job.tenant_id == tenant_id]
        if not include_archived:
            filters.append(Job.archived_at.is_(None))
        if status:
            try:
                filters.append(Job.status == normalize_status(status))
            except ValueError as exc:
                raise CrmError("invalid_status", f"Unknown status: {status}") from exc
        if priority:
            try:
                filters.append(Job.priority == normalize_priority(priority))
            except ValueError as exc:
                raise CrmError(
                    "invalid_priority", f"Unknown priority: {priority}"
                ) from exc
        if customer_id is not None:
            filters.append(Job.customer_id == customer_id)
        if technician_id is not None:
            filters.append(Job.assigned_technician_id == technician_id)
        if service_id is not None:
            filters.append(Job.service_id == service_id)
        if location_id is not None:
            filters.append(Job.location_id == location_id)
        if scheduled_from is not None:
            filters.append(Job.scheduled_starts_at >= scheduled_from)
        if scheduled_to is not None:
            filters.append(Job.scheduled_starts_at <= scheduled_to)

        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(Job.job_number).like(term),
                    func.lower(Job.reference_code).like(term),
                    func.lower(func.coalesce(Job.description, "")).like(term),
                    func.lower(Job.service_type).like(term),
                    Job.customer_id.in_(
                        select(Customer.id).where(
                            Customer.tenant_id == tenant_id,
                            func.lower(Customer.name).like(term),
                        )
                    ),
                )
            )

        stmt = (
            select(Job)
            .where(and_(*filters))
            .options(
                selectinload(Job.customer),
                selectinload(Job.assigned_technician),
                selectinload(Job.location),
                selectinload(Job.service),
            )
            .order_by(Job.created_at.desc(), Job.id.desc())
        )
        if decoded is not None:
            stmt = stmt.where(
                or_(
                    Job.created_at < decoded.created_at,
                    and_(
                        Job.created_at == decoded.created_at,
                        Job.id < decoded.id,
                    ),
                )
            )
        stmt = stmt.limit(page.limit + 1)
        rows = list(self._session.scalars(stmt).all())
        next_cursor = None
        if len(rows) > page.limit:
            last = rows[page.limit - 1]
            next_cursor = JobCursor(created_at=last.created_at, id=last.id).encode()
            rows = rows[: page.limit]

        return {
            "jobs": [serialize_job(r) for r in rows],
            "next_cursor": next_cursor,
            "limit": page.limit,
        }
