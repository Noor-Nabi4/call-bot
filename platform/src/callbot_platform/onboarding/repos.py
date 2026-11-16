"""Organization onboarding repository — always tenant-scoped."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.onboarding import OrganizationOnboarding
from callbot_platform.onboarding.status import STATUS_NOT_STARTED


class OnboardingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, tenant_id: UUID) -> OrganizationOnboarding | None:
        return self._session.scalar(
            select(OrganizationOnboarding).where(
                OrganizationOnboarding.tenant_id == tenant_id
            )
        )

    def get_for_update(self, tenant_id: UUID) -> OrganizationOnboarding | None:
        """Load row with FOR UPDATE when supported (best-effort on SQLite)."""
        return self._session.scalar(
            select(OrganizationOnboarding)
            .where(OrganizationOnboarding.tenant_id == tenant_id)
            .with_for_update()
        )

    def ensure(
        self, tenant_id: UUID, *, for_update: bool = False
    ) -> OrganizationOnboarding:
        row = self.get_for_update(tenant_id) if for_update else self.get(tenant_id)
        if row is not None:
            return row
        row = OrganizationOnboarding(
            tenant_id=tenant_id,
            status=STATUS_NOT_STARTED,
            current_step=None,
            completed_steps=[],
            skipped_steps=[],
            progress_percent=0,
            state_data={},
        )
        self._session.add(row)
        self._session.flush()
        if for_update:
            locked = self.get_for_update(tenant_id)
            if locked is not None:
                return locked
        return row

    def touch(self, row: OrganizationOnboarding) -> None:
        row.updated_at = datetime.now(UTC)
        self._session.flush()

    def serialize_row_meta(self, row: OrganizationOnboarding) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "tenant_id": str(row.tenant_id),
            "started_at": row.started_at.isoformat() if row.started_at else None,
            "completed_at": row.completed_at.isoformat() if row.completed_at else None,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
