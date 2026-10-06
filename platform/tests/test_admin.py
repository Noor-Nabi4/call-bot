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


def test_list_calls_status_filter_for_live_monitor(
    session: Session, tenant: Tenant
) -> None:
    repo = CallRepository(session)
    active = repo.start(
        tenant.id,
        room_name="live-room",
        caller_number="+15550003333",
        called_number="+15550004444",
    )
    ended = repo.start(
        tenant.id,
        room_name="ended-room",
        caller_number="+15550005555",
    )
    repo.end(
        tenant.id,
        call_id=uuid.UUID(ended["id"]),
        status="closed",
        disconnect_reason="completed",
        metrics={"handoff_requested": True},
    )

    admin = AdminRepository(session)
    live = admin.list_calls(tenant.id, status="active")
    assert len(live["calls"]) == 1
    assert live["calls"][0]["id"] == active["id"]
    assert live["calls"][0]["status"] == "active"
    assert live["calls"][0]["elapsed_seconds"] is not None
    assert live["calls"][0]["elapsed_seconds"] >= 0
    assert live["calls"][0]["handoff_requested"] is False

    closed = admin.list_calls(tenant.id, status="closed")
    assert any(c["id"] == ended["id"] for c in closed["calls"])
    closed_row = next(c for c in closed["calls"] if c["id"] == ended["id"])
    assert closed_row["handoff_requested"] is True


def test_supervisor_snapshot(session: Session, tenant: Tenant) -> None:
    repo = CallRepository(session)
    active = repo.start(
        tenant.id,
        room_name="sup-active",
        caller_number="+15550006666",
    )
    active_id = uuid.UUID(active["id"])
    row = session.get(Call, active_id)
    assert row is not None
    row.metrics = {"handoff_requested": True}
    session.flush()

    closed = repo.start(
        tenant.id,
        room_name="sup-closed",
        caller_number="+15550007777",
    )
    repo.end(
        tenant.id,
        call_id=uuid.UUID(closed["id"]),
        status="closed",
        disconnect_reason="completed",
        metrics={},
    )

    snap = AdminRepository(session).supervisor_snapshot(tenant.id, recent_limit=10)
    assert snap["summary"]["calls_active"] == 1
    assert snap["summary"]["handoffs_open"] == 1
    assert snap["summary"]["calls_today"] >= 2
    assert len(snap["active_calls"]) == 1
    assert snap["active_calls"][0]["id"] == active["id"]
    assert len(snap["attention"]) == 1
    assert any(c["id"] == closed["id"] for c in snap["recent_calls"])
    assert all(c["status"] != "active" for c in snap["recent_calls"])
