"""Admin metrics and retention tests."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from callbot_platform.admin.repos import AdminRepository
from callbot_platform.auth.repos import AuthRepository
from callbot_platform.crm.repos import CallRepository, CustomerRepository
from callbot_platform.db.models import Call, Tenant


def test_metrics_and_retention(session: Session, tenant: Tenant) -> None:
    AuthRepository(session).bootstrap_admin(
        tenant_id=tenant.id,
        email="admin@t.test",
        password="password123",
        name="Admin",
    )
    CustomerRepository(session).upsert(tenant.id, name="Cust", phone="+15550001111")
    admin = AdminRepository(session)
    metrics = admin.metrics_summary(tenant.id, days=30)
    assert metrics["customers"] >= 1
    settings = admin.upsert_retention(
        tenant.id, recording_retention_days=14, actor="admin@t.test"
    )
    assert settings["recording_retention_days"] == 14
    users = admin.list_users(tenant.id)
    assert any(u["email"] == "admin@t.test" for u in users)


def test_advanced_call_metrics(session: Session, tenant: Tenant) -> None:
    repo = CallRepository(session)
    started = repo.start(
        tenant.id,
        room_name="metrics-room",
        caller_number="+15550002222",
    )
    call_id = uuid.UUID(started["id"])
    row = session.get(Call, call_id)
    assert row is not None
    row.started_at = datetime.now(UTC) - timedelta(seconds=120)
    session.flush()
    repo.end(
        tenant.id,
        call_id=call_id,
        status="closed",
        disconnect_reason="participant_disconnected",
        metrics={"handoff_requested": True, "appointment_booked": False},
    )

    metrics = AdminRepository(session).metrics_summary(tenant.id, days=7)
    assert metrics["calls"] >= 1
    assert metrics["calls_ended"] >= 1
    assert metrics["voice_seconds"] >= 120
    assert metrics["voice_minutes"] >= 2
    assert metrics["handoffs_requested"] >= 1
    assert metrics["handoff_rate"] > 0
    assert "participant_disconnected" in metrics["disconnect_reasons"]
    assert isinstance(metrics["calls_by_day"], list)
    assert len(metrics["calls_by_day"]) >= 1
