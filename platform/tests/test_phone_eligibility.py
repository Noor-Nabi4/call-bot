"""Inbound phone eligibility for mandatory onboarding."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from callbot_platform.db.models import Tenant
from callbot_platform.domain.enums import ConnectionStatus, VerificationStatus
from callbot_platform.telephony.eligibility import (
    phone_setup_readiness,
    tenant_has_eligible_inbound_number,
)
from helpers import make_phone


def test_eligible_requires_active_verified_and_livekit(session: Session) -> None:
    tenant = Tenant(name="Elig", slug=f"elig-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    assert tenant_has_eligible_inbound_number(session, tenant.id) is False
    row = make_phone(
        session,
        tenant,
        e164=f"+1555{uuid.uuid4().hex[:7]}",
        trunk_id=None,
        dispatch_id=None,
    )
    assert tenant_has_eligible_inbound_number(session, tenant.id) is False
    row.livekit_inbound_trunk_id = "ST_t"
    row.livekit_dispatch_rule_id = "SDR_r"
    session.flush()
    assert tenant_has_eligible_inbound_number(session, tenant.id) is True
    ready = phone_setup_readiness(session, tenant.id)
    assert ready["state"] == "ready"
    assert ready["eligible_count"] == 1


def test_pending_and_released_states(session: Session) -> None:
    tenant = Tenant(name="Pending", slug=f"pend-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    make_phone(
        session,
        tenant,
        e164=f"+1555{uuid.uuid4().hex[:7]}",
        connection_status=ConnectionStatus.PENDING_VERIFICATION.value,
        verification_status=VerificationStatus.PENDING.value,
    )
    pending = phone_setup_readiness(session, tenant.id)
    assert pending["state"] == "setup_in_progress"

    other = Tenant(name="Released", slug=f"rel-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    make_phone(
        session,
        other,
        e164=f"+1555{uuid.uuid4().hex[:7]}",
        connection_status=ConnectionStatus.RELEASED.value,
        verification_status=VerificationStatus.VERIFIED.value,
    )
    released = phone_setup_readiness(session, other.id)
    assert released["state"] == "action_required"
