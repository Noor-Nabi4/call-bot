"""Handoff settings tests."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from callbot_platform.db.models import Tenant
from callbot_platform.handoff.repos import HandoffRepository


def test_handoff_upsert_and_get(session: Session, tenant: Tenant) -> None:
    repo = HandoffRepository(session)
    default = repo.get(tenant.id)
    assert default["enabled"] is False
    updated = repo.upsert(
        tenant.id,
        enabled=True,
        mode="cold",
        escalation_phone_e164="+15551239999",
        sip_outbound_trunk_id="ST_out_123",
    )
    assert updated["enabled"] is True
    assert updated["mode"] == "cold"
    assert updated["escalation_phone_e164"] == "+15551239999"
    assert repo.get(tenant.id)["sip_outbound_trunk_id"] == "ST_out_123"


def test_handoff_tenant_isolation(session: Session, tenant: Tenant) -> None:
    other = Tenant(name="Other", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    HandoffRepository(session).upsert(
        tenant.id, enabled=True, escalation_phone_e164="+15551110000"
    )
    assert HandoffRepository(session).get(other.id)["enabled"] is False
    assert HandoffRepository(session).get(other.id)["escalation_phone_e164"] is None
