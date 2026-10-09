"""Authoritative application access checks (onboarding + phone eligibility)."""

from __future__ import annotations

from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from callbot_platform.onboarding.repos import OnboardingRepository
from callbot_platform.onboarding.status import STATUS_COMPLETED

# Business onboarding terminal status that is a prerequisite for access.
ONBOARDING_SATISFIED_STATUSES = frozenset({STATUS_COMPLETED})

ONBOARDING_REQUIRED_DETAIL = {
    "code": "ONBOARDING_REQUIRED",
    "reason": "business_incomplete",
    "message": "Complete organization onboarding before using the application.",
}

PHONE_SETUP_REQUIRED_DETAIL = {
    "code": "ONBOARDING_REQUIRED",
    "reason": "phone_required",
    "message": (
        "Configure at least one verified inbound phone number "
        "before using the application."
    ),
}


def onboarding_status_for_tenant(session: Session, tenant_id: UUID) -> str | None:
    """Return persisted status, or None when no onboarding row exists.

    Missing rows are incomplete — never treat absence as completed.
    """
    row = OnboardingRepository(session).get(tenant_id)
    if row is None:
        return None
    return str(row.status)


def is_business_onboarding_complete(session: Session, tenant_id: UUID) -> bool:
    status = onboarding_status_for_tenant(session, tenant_id)
    return status in ONBOARDING_SATISFIED_STATUSES


def is_phone_ready_for_tenant(session: Session, tenant_id: UUID) -> bool:
    from callbot_platform.telephony.eligibility import (
        tenant_has_eligible_inbound_number,
    )

    return tenant_has_eligible_inbound_number(session, tenant_id)


def is_onboarding_satisfied(session: Session, tenant_id: UUID) -> bool:
    """Application access: COMPLETED business onboarding AND eligible phone.

    Historical COMPLETED rows without an eligible number do not grant access.
    Losing the last eligible number blocks access again without rewriting
    OrganizationOnboarding.status.
    """
    if not is_business_onboarding_complete(session, tenant_id):
        return False
    return is_phone_ready_for_tenant(session, tenant_id)


def access_block_detail(session: Session, tenant_id: UUID) -> dict[str, str]:
    """Structured 403 detail when access is blocked."""
    if not is_business_onboarding_complete(session, tenant_id):
        return dict(ONBOARDING_REQUIRED_DETAIL)
    if not is_phone_ready_for_tenant(session, tenant_id):
        return dict(PHONE_SETUP_REQUIRED_DETAIL)
    return dict(ONBOARDING_REQUIRED_DETAIL)


def assert_onboarding_satisfied(session: Session, tenant_id: UUID) -> None:
    if not is_onboarding_satisfied(session, tenant_id):
        raise HTTPException(
            status_code=403, detail=access_block_detail(session, tenant_id)
        )


def mark_legacy_tenant_onboarding_complete(
    session: Session, tenant_id: UUID
) -> None:
    """Test/migration helper: ensure a COMPLETED onboarding row exists.

    Does not create a phone number — call sites that need full app access
    must also provision an eligible TenantPhoneNumber.
    """
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
