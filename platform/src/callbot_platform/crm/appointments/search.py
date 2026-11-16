"""Server-side appointment search and filters."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import and_, func, or_, select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.appointments.constants import (
    normalize_priority,
    normalize_status,
)
from callbot_platform.crm.appointments.cursors import (
    AppointmentCursor,
    parse_appointment_page,
)
from callbot_platform.crm.appointments.serialize import serialize_appointment
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import Customer
from callbot_platform.db.models.scheduling import Appointment


class AppointmentSearchService:
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
        job_id: UUID | None = None,
        is_emergency: bool | None = None,
        starts_from: datetime | None = None,
        starts_to: datetime | None = None,
        include_archived: bool = False,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        try:
            page, decoded = parse_appointment_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        filters = [Appointment.tenant_id == tenant_id]
        if not include_archived:
            filters.append(Appointment.archived_at.is_(None))
        if status:
            try:
                filters.append(Appointment.status == normalize_status(status))
            except ValueError as exc:
                raise CrmError("invalid_status", f"Unknown status: {status}") from exc
        if priority:
            try:
                filters.append(Appointment.priority == normalize_priority(priority))
            except ValueError as exc:
                raise CrmError(
                    "invalid_priority", f"Unknown priority: {priority}"
                ) from exc
        if customer_id is not None:
            filters.append(Appointment.customer_id == customer_id)
        if technician_id is not None:
            filters.append(Appointment.assigned_technician_id == technician_id)
        if service_id is not None:
            filters.append(Appointment.service_id == service_id)
        if location_id is not None:
            filters.append(Appointment.location_id == location_id)
        if job_id is not None:
            filters.append(Appointment.job_id == job_id)
        if is_emergency is not None:
            filters.append(Appointment.is_emergency.is_(is_emergency))
        if starts_from is not None:
            filters.append(Appointment.starts_at >= starts_from)
        if starts_to is not None:
            filters.append(Appointment.starts_at <= starts_to)

        if q and q.strip():
            term = f"%{q.strip().lower()}%"
            filters.append(
                or_(
                    func.lower(Appointment.appointment_number).like(term),
                    func.lower(Appointment.confirmation_code).like(term),
                    func.lower(Appointment.service_type).like(term),
                    func.lower(func.coalesce(Appointment.notes, "")).like(term),
                    Appointment.customer_id.in_(
                        select(Customer.id).where(
                            Customer.tenant_id == tenant_id,
                            func.lower(Customer.name).like(term),
                        )
                    ),
                )
            )

        stmt = (
            select(Appointment)
            .where(and_(*filters))
            .options(
                selectinload(Appointment.customer),
                selectinload(Appointment.assigned_technician),
                selectinload(Appointment.location),
                selectinload(Appointment.service),
            )
            .order_by(Appointment.starts_at.asc(), Appointment.id.asc())
        )
        if decoded is not None:
            stmt = stmt.where(
                or_(
                    Appointment.starts_at > decoded.starts_at,
                    and_(
                        Appointment.starts_at == decoded.starts_at,
                        Appointment.id > decoded.id,
                    ),
                )
            )
        stmt = stmt.limit(page.limit + 1)
        rows = list(self._session.scalars(stmt).all())
        next_cursor = None
        if len(rows) > page.limit:
            last = rows[page.limit - 1]
            next_cursor = AppointmentCursor(
                starts_at=last.starts_at, id=last.id
            ).encode()
            rows = rows[: page.limit]

        return {
            "appointments": [serialize_appointment(r) for r in rows],
            "next_cursor": next_cursor,
            "limit": page.limit,
        }
