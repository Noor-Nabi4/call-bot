"""Tenant departments for handoff routing."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.db.models.human_handoff import Department
from callbot_platform.human_handoff.constants import DEFAULT_DEPARTMENTS
from callbot_platform.human_handoff.errors import HandoffDomainError
from callbot_platform.telephony.audit import write_audit


def serialize_department(row: Department) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "name": row.name,
        "slug": row.slug,
        "phone_e164": row.phone_e164,
        "active": row.active,
        "sort_order": row.sort_order,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


class DepartmentService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def ensure_defaults(self, tenant_id: UUID, *, actor: str = "system") -> list[dict]:
        existing = {
            r.slug
            for r in self._session.scalars(
                select(Department).where(Department.tenant_id == tenant_id)
            ).all()
        }
        created: list[dict] = []
        for name, slug, order in DEFAULT_DEPARTMENTS:
            if slug in existing:
                continue
            row = Department(
                tenant_id=tenant_id,
                name=name,
                slug=slug,
                active=True,
                sort_order=order,
            )
            try:
                with self._session.begin_nested():
                    self._session.add(row)
                    self._session.flush()
            except IntegrityError:
                self._session.expire_all()
                continue
            created.append(serialize_department(row))
        if created:
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="departments.seeded",
                resource_ids={"count": len(created)},
                payload_summary={},
            )
        return created

    def list(self, tenant_id: UUID, *, active_only: bool = True) -> list[dict]:
        self.ensure_defaults(tenant_id)
        stmt = select(Department).where(Department.tenant_id == tenant_id)
        if active_only:
            stmt = stmt.where(Department.active.is_(True))
        rows = list(
            self._session.scalars(stmt.order_by(Department.sort_order.asc())).all()
        )
        return [serialize_department(r) for r in rows]

    def get_by_slug(self, tenant_id: UUID, slug: str) -> Department | None:
        self.ensure_defaults(tenant_id)
        return self._session.scalar(
            select(Department).where(
                Department.tenant_id == tenant_id,
                Department.slug == slug.strip().lower(),
                Department.active.is_(True),
            )
        )

    def get(self, tenant_id: UUID, department_id: UUID) -> Department | None:
        return self._session.scalar(
            select(Department).where(
                Department.id == department_id, Department.tenant_id == tenant_id
            )
        )

    def upsert(
        self,
        tenant_id: UUID,
        *,
        slug: str,
        name: str,
        actor: str,
        phone_e164: str | None = None,
        active: bool = True,
    ) -> dict[str, Any]:
        slug_n = slug.strip().lower()
        if slug_n not in {s for _, s, _ in DEFAULT_DEPARTMENTS} and slug_n != "other":
            raise HandoffDomainError("invalid_department", "Unknown department slug")
        row = self._session.scalar(
            select(Department).where(
                Department.tenant_id == tenant_id, Department.slug == slug_n
            )
        )
        now = datetime.now(UTC)
        if row is None:
            row = Department(
                tenant_id=tenant_id,
                name=name.strip()[:128],
                slug=slug_n,
                phone_e164=phone_e164,
                active=active,
            )
            self._session.add(row)
        else:
            row.name = name.strip()[:128]
            row.phone_e164 = phone_e164
            row.active = active
            row.updated_at = now
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="department.upserted",
            resource_ids={"department_id": str(row.id)},
            payload_summary={"slug": row.slug, "active": row.active},
        )
        return serialize_department(row)
