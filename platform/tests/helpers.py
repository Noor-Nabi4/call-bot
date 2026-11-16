"""Test helpers shared across telephony tests."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from callbot_platform.db.models import Tenant, TenantPhoneNumber
from callbot_platform.domain.enums import (
    AuthMethod,
    ConnectionStatus,
    OnboardingPath,
    ProvisioningState,
    VerificationStatus,
)
from callbot_platform.onboarding.access import mark_legacy_tenant_onboarding_complete


def next_open_booking_day(*, after: date | None = None) -> date:
    """Next weekday on or after tomorrow (UTC), inside the default 14-day horizon."""
    day = (after or datetime.now(UTC).date()) + timedelta(days=1)
    while day.weekday() >= 5:
        day += timedelta(days=1)
    return day


def make_phone(
    session: Session,
    tenant: Tenant,
    *,
    e164: str = "+15551234567",
    connection_status: str = ConnectionStatus.ACTIVE.value,
    verification_status: str = VerificationStatus.VERIFIED.value,
    trunk_id: str | None = "ST_trunk_1",
    dispatch_id: str | None = "SDR_rule_1",
) -> TenantPhoneNumber:
    row = TenantPhoneNumber(
        tenant_id=tenant.id,
        provider="twilio",
        e164=e164,
        livekit_inbound_trunk_id=trunk_id,
        livekit_dispatch_rule_id=dispatch_id,
        connection_status=connection_status,
        verification_status=verification_status,
        onboarding_path=OnboardingPath.CONNECT_EXISTING.value,
        auth_method=AuthMethod.MANUAL.value,
        provisioning_state=ProvisioningState.COMPLETE.value,
        provisioning_details={},
    )
    session.add(row)
    session.flush()
    return row


def establish_tenant_access(
    session: Session,
    tenant: Tenant,
    *,
    e164: str | None = None,
) -> TenantPhoneNumber:
    """Mark business onboarding COMPLETED and attach an eligible inbound DID.

    HTTP tests that authenticate as a secondary tenant must call this so the
    phone gate does not return 403 before tenant-isolation checks run.
    """
    mark_legacy_tenant_onboarding_complete(session, tenant.id)
    return make_phone(
        session,
        tenant,
        e164=e164 or f"+1555{uuid.uuid4().hex[:7]}",
    )
