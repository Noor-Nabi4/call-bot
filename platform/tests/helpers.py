"""Test helpers shared across telephony tests."""

from __future__ import annotations

from sqlalchemy.orm import Session

from callbot_platform.db.models import Tenant, TenantPhoneNumber
from callbot_platform.domain.enums import (
    AuthMethod,
    ConnectionStatus,
    OnboardingPath,
    ProvisioningState,
    VerificationStatus,
)


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
