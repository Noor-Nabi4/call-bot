"""Automation rule tests."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from callbot_platform.automation.service import AutomationService
from callbot_platform.crm.repos import CallRepository, CustomerRepository
from callbot_platform.db.models import Tenant


def test_handoff_rule_writes_audit_and_creates_job(
    session: Session, tenant: Tenant
) -> None:
    customer = CustomerRepository(session).upsert(
        tenant.id, name="Pat", phone="+15553334444"
    )
    service = AutomationService(session)
    service.create_rule(
        tenant.id,
        name="Handoff follow-up",
        trigger_key="call.handoff_requested",
        action_key="create_follow_up_job",
        config={"service_type": "Handoff follow-up"},
    )
    service.create_rule(
        tenant.id,
        name="Log every handoff",
        trigger_key="call.handoff_requested",
        action_key="write_audit",
    )

    started = CallRepository(session).start(
        tenant.id,
        room_name="auto-room",
        customer_id=uuid.UUID(customer["id"]),
        caller_number="+15553334444",
    )
    ended = CallRepository(session).end(
        tenant.id,
        call_id=uuid.UUID(started["id"]),
        status="closed",
        metrics={"handoff_requested": True},
        customer_id=uuid.UUID(customer["id"]),
    )
    results = service.dispatch(
        tenant.id,
        "call.handoff_requested",
        payload={
            "call_id": ended["id"],
            "customer_id": ended["customer_id"],
        },
    )
    assert len(results) == 2
    assert all(r["ok"] for r in results)
    assert any(r.get("result", {}).get("job_id") for r in results)


def test_disabled_rule_does_not_fire(session: Session, tenant: Tenant) -> None:
    service = AutomationService(session)
    rule = service.create_rule(
        tenant.id,
        name="Disabled",
        trigger_key="call.ended",
        action_key="write_audit",
        is_enabled=False,
    )
    results = service.dispatch(
        tenant.id, "call.ended", payload={"call_id": str(uuid.uuid4())}
    )
    assert results == []
    service.update_rule(tenant.id, uuid.UUID(rule["id"]), is_enabled=True, actor="test")
    results = service.dispatch(
        tenant.id, "call.ended", payload={"call_id": str(uuid.uuid4())}
    )
    assert len(results) == 1 and results[0]["ok"]
