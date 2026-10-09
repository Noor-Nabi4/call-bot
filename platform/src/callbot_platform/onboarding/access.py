"""Authoritative onboarding completion checks for API/route gates."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from callbot_platform.onboarding.repos import OnboardingRepository
from callbot_platform.onboarding.status import STATUS_COMPLETED

# Mandatory onboarding: only COMPLETED satisfies the application gate.
# SKIPPED is retained as a historical status but does not grant access.
ONBOARDING_SATISFIED_STATUSES = frozenset({STATUS_COMPLETED})

ONBOARDING_REQUIRED_DETAIL = {
    "code": "ONBOARDING_REQUIRED",
    "message": "Complete organization onboarding before using the application.",
}


def onboarding_status_for_tenant(session: Session, tenant_id: UUID) -> str | None:
    """Return persisted status, or None when no onboarding row exists.

    Missing rows are incomplete — never treat absence as completed.
    """
    row = OnboardingRepository(session).get(tenant_id)
    if row is None:
        return None
    return str(row.status)


def is_onboarding_satisfied(session: Session, tenant_id: UUID) -> bool:
    status = onboarding_status_for_tenant(session, tenant_id)
    return status in ONBOARDING_SATISFIED_STATUSES


def assert_onboarding_satisfied(session: Session, tenant_id: UUID) -> None:
    if not is_onboarding_satisfied(session, tenant_id):
        raise HTTPException(status_code=403, detail=dict(ONBOARDING_REQUIRED_DETAIL))


def mark_legacy_tenant_onboarding_complete(
    session: Session, tenant_id: UUID
) -> None:
    """Test/migration helper: ensure a COMPLETED onboarding row exists."""
    from datetime import UTC, datetime

    from callbot_platform.onboarding.status import STATUS_NOT_STARTED

    repo = OnboardingRepository(session)
    row = repo.get(tenant_id)
    if row is None:
        row = repo.ensure(tenant_id)
    if row.status == STATUS_COMPLETED:
        return
    if row.status == STATUS_NOT_STARTED or row.started_at is None:
        row.started_at = datetime.now(UTC)
    row.status = STATUS_COMPLETED
    row.completed_at = datetime.now(UTC)
    row.progress_percent = 100
    repo.touch(row)
