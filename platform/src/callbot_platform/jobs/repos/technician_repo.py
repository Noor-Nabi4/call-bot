"""Technician repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models import Technician
from callbot_platform.jobs.errors import JobsError
from callbot_platform.security.session import ROLE_TECHNICIAN


class TechnicianRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list(
        self, tenant_id: UUID, *, active_only: bool = True
    ) -> list[dict[str, Any]]:
        q = select(Technician).where(Technician.tenant_id == tenant_id)
        if active_only:
            q = q.where(Technician.is_active.is_(True))
        rows = self._session.scalars(q.order_by(Technician.display_name)).all()
        return [self._serialize(r) for r in rows]

    def create(
        self,
        tenant_id: UUID,
        *,
        email: str,
        password: str,
        name: str,
        phone: str | None = None,
        actor: str = "dispatcher",
    ) -> dict[str, Any]:
        from callbot_platform.auth.repos import AuthRepository

        user = AuthRepository(self._session).create_user(
            tenant_id,
            email=email,
            password=password,
            name=name,
            role=ROLE_TECHNICIAN,
            phone=phone,
            actor=actor,
        )
        tech_id = user.get("technician_id")
        if not tech_id:
            raise JobsError("tech_create_failed", "Technician profile was not created")
        tech = self._session.scalar(
            select(Technician).where(
                Technician.id == UUID(tech_id),
                Technician.tenant_id == tenant_id,
            )
        )
        if tech is None:
            raise JobsError("tech_create_failed", "Technician profile was not created")
        from callbot_platform.crm.dispatch.status import TechnicianStatusService

        TechnicianStatusService(self._session).ensure_row(
            tenant_id,
            tech.id,
            actor=actor,
            initial_status="AVAILABLE" if tech.is_active else "OFFLINE",
        )
        return self._serialize(tech)

    def update_location(
        self,
        tenant_id: UUID,
        technician_id: UUID,
        *,
        lat: float,
        lng: float,
    ) -> dict[str, Any]:
        tech = self._session.scalar(
            select(Technician).where(
                Technician.id == technician_id, Technician.tenant_id == tenant_id
            )
        )
        if tech is None:
            raise JobsError("technician_not_found", "Technician not found")
        tech.last_lat = lat
        tech.last_lng = lng
        tech.last_location_at = datetime.now(UTC)
        tech.updated_at = datetime.now(UTC)
        self._session.flush()
        return self._serialize(tech)

    def _serialize(self, tech: Technician) -> dict[str, Any]:
        return {
            "id": str(tech.id),
            "tenant_id": str(tech.tenant_id),
            "user_id": str(tech.user_id),
            "display_name": tech.display_name,
            "phone": tech.phone,
            "is_active": tech.is_active,
            "last_lat": tech.last_lat,
            "last_lng": tech.last_lng,
            "last_location_at": (
                tech.last_location_at.isoformat() if tech.last_location_at else None
            ),
        }
