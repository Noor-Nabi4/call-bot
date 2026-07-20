"""Call queue repository tests."""

from __future__ import annotations

import uuid

from sqlalchemy.orm import Session

from callbot_platform.crm.repos import CallRepository
from callbot_platform.db.models import Tenant
from callbot_platform.queue import CallQueueRepository


def test_enqueue_claim_complete(session: Session, tenant: Tenant) -> None:
    call = CallRepository(session).start(
        tenant.id, room_name="queue-room", caller_number="+15550009999"
    )
    call_id = uuid.UUID(call["id"])
    CallRepository(session).end(
        tenant.id,
        call_id=call_id,
        status="closed",
        disconnect_reason="completed",
        metrics={"handoff_requested": True},
    )

    queue = CallQueueRepository(session)
    item = queue.enqueue_for_call(
        tenant.id, call_id, reason="handoff", priority=10, actor="system"
    )
    assert item is not None
    assert item["status"] == "waiting"
    assert item["caller_number"] == "+15550009999"

    # Idempotent
    again = queue.enqueue_for_call(tenant.id, call_id, actor="system")
    assert again is not None
    assert again["id"] == item["id"]

    waiting = queue.list_items(tenant.id, status="waiting")
    assert len(waiting) == 1

    claimed = queue.claim(tenant.id, uuid.UUID(item["id"]), actor="dispatcher@t.test")
    assert claimed["status"] == "claimed"
    assert claimed["claimed_by"] == "dispatcher@t.test"

    done = queue.complete(
        tenant.id,
        uuid.UUID(item["id"]),
        actor="dispatcher@t.test",
        notes="Caller reached",
    )
    assert done["status"] == "done"
    assert done["notes"] == "Caller reached"
    assert queue.list_items(tenant.id, status="waiting") == []
