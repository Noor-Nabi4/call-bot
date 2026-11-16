"""Tenant-scoped inbound phone eligibility (aligned with DID resolver)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models import TenantPhoneNumber
from callbot_platform.domain.enums import ConnectionStatus, VerificationStatus

# States that mean setup started but inbound is not ready yet.
_PENDING_CONNECTION = frozenset(
    {
        ConnectionStatus.PENDING_SETUP.value,
        ConnectionStatus.CONFIGURING.value,
        ConnectionStatus.PENDING_VERIFICATION.value,
        ConnectionStatus.PARTIAL.value,
    }
)


def list_eligible_inbound_numbers(
    session: Session, tenant_id: UUID
) -> list[TenantPhoneNumber]:
    """Numbers usable for inbound voice — same bar as DbTenantDidResolver."""
    rows = session.scalars(
        select(TenantPhoneNumber)
        .where(
            TenantPhoneNumber.tenant_id == tenant_id,
            TenantPhoneNumber.connection_status == ConnectionStatus.ACTIVE.value,
            TenantPhoneNumber.verification_status
            == VerificationStatus.VERIFIED.value,
            TenantPhoneNumber.livekit_inbound_trunk_id.is_not(None),
            TenantPhoneNumber.livekit_dispatch_rule_id.is_not(None),
        )
        .order_by(TenantPhoneNumber.created_at.asc())
    ).all()
    return list(rows)


def tenant_has_eligible_inbound_number(session: Session, tenant_id: UUID) -> bool:
    return bool(list_eligible_inbound_numbers(session, tenant_id))


def phone_setup_readiness(session: Session, tenant_id: UUID) -> dict[str, Any]:
    """Authoritative phone-setup state for onboarding UI/API."""
    eligible = list_eligible_inbound_numbers(session, tenant_id)
    if eligible:
        first = eligible[0]
        return {
            "state": "ready",
            "eligible_count": len(eligible),
            "primary_e164": first.e164,
            "primary_phone_number_id": str(first.id),
            "message": "An inbound phone number is ready.",
        }

    rows = session.scalars(
        select(TenantPhoneNumber).where(TenantPhoneNumber.tenant_id == tenant_id)
    ).all()
    if not rows:
        return {
            "state": "not_configured",
            "eligible_count": 0,
            "primary_e164": None,
            "primary_phone_number_id": None,
            "message": "Configure at least one inbound phone number to finish setup.",
        }

    pending = [
        r
        for r in rows
        if r.connection_status in _PENDING_CONNECTION
        or r.verification_status
        in {
            VerificationStatus.UNVERIFIED.value,
            VerificationStatus.PENDING.value,
        }
    ]
    if pending:
        row = pending[0]
        if row.verification_status == VerificationStatus.PENDING.value:
            message = (
                f"Call {row.e164} from another phone now. "
                "After we detect the inbound call, this number becomes Active "
                "and you can finish onboarding."
            )
        elif row.connection_status == ConnectionStatus.PENDING_VERIFICATION.value:
            message = (
                f"Start verification for {row.e164}, then call that number "
                "from another phone so we can mark it Active."
            )
        else:
            message = (
                "Phone number setup is still in progress. "
                "Finish provisioning and verification before continuing."
            )
        return {
            "state": "setup_in_progress",
            "eligible_count": 0,
            "primary_e164": row.e164,
            "primary_phone_number_id": str(row.id),
            "connection_status": row.connection_status,
            "verification_status": row.verification_status,
            "message": message,
        }

    failed = [
        r
        for r in rows
        if r.connection_status
        in {
            ConnectionStatus.FAILED.value,
            ConnectionStatus.RELEASED.value,
            ConnectionStatus.RELEASING.value,
        }
        or r.verification_status == VerificationStatus.FAILED.value
    ]
    if failed:
        row = failed[0]
        return {
            "state": "action_required",
            "eligible_count": 0,
            "primary_e164": row.e164,
            "primary_phone_number_id": str(row.id),
            "connection_status": row.connection_status,
            "verification_status": row.verification_status,
            "message": (
                "The configured phone number is not usable. "
                "Fix or replace it before finishing onboarding."
            ),
        }

    row = rows[0]
    return {
        "state": "action_required",
        "eligible_count": 0,
        "primary_e164": row.e164,
        "primary_phone_number_id": str(row.id),
        "connection_status": row.connection_status,
        "verification_status": row.verification_status,
        "message": "Phone number is not eligible for inbound calling yet.",
    }
