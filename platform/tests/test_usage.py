"""Tests for tenant usage metering."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from callbot_platform.billing.plans import entitlements_for_plan
from callbot_platform.billing.repos import BillingRepository
from callbot_platform.billing.usage import (
    UsageService,
    calendar_month_bounds,
    compute_billable_seconds,
    seconds_to_billable_minutes,
)
from callbot_platform.crm.repos.call_repo import CallRepository
from callbot_platform.db.models import Tenant


def test_compute_billable_seconds_ceil() -> None:
    start = datetime(2026, 7, 1, 12, 0, 0, tzinfo=UTC)
    end = start + timedelta(seconds=90.2)
    assert compute_billable_seconds(start, end) == 91
    assert compute_billable_seconds(start, start) == 0
    assert seconds_to_billable_minutes(61) == 2
    assert seconds_to_billable_minutes(60) == 1
    assert seconds_to_billable_minutes(0) == 0


def test_calendar_month_bounds() -> None:
    start, end = calendar_month_bounds(datetime(2026, 7, 20, 15, 0, tzinfo=UTC))
    assert start == datetime(2026, 7, 1, tzinfo=UTC)
    assert end == datetime(2026, 8, 1, tzinfo=UTC)


def test_call_end_records_billable_seconds(session: Session, tenant: Tenant) -> None:
    started = CallRepository(session).start(
        tenant.id,
        room_name="usage-call",
        job_id="AJ_usage",
        caller_number="+15550001111",
    )
    call_id = uuid.UUID(started["id"])
    from callbot_platform.db.models import Call

    row = session.get(Call, call_id)
    assert row is not None
    row.started_at = datetime.now(UTC) - timedelta(seconds=125)
    session.flush()

    ended = CallRepository(session).end(
        tenant.id,
        call_id=call_id,
        status="closed",
    )
    assert ended["billable_seconds"] is not None
    assert ended["billable_seconds"] >= 125


def test_usage_summary_aggregates_minutes(session: Session, tenant: Tenant) -> None:
    BillingRepository(session).create_incomplete(
        tenant_id=tenant.id,
        stripe_customer_id=f"cus_{uuid.uuid4().hex[:12]}",
        plan_key="starter",
    )
    repo = CallRepository(session)
    for seconds in (60, 90):
        started = repo.start(
            tenant.id,
            room_name=f"room-{seconds}",
            caller_number="+15550002222",
        )
        call_id = uuid.UUID(started["id"])
        from callbot_platform.db.models import Call

        row = session.get(Call, call_id)
        assert row is not None
        row.started_at = datetime.now(UTC) - timedelta(seconds=seconds)
        session.flush()
        repo.end(tenant.id, call_id=call_id, status="closed")

    summary = UsageService(session).usage_summary(tenant.id)
    assert summary["plan_key"] == "starter"
    assert summary["call_count"] == 2
    assert summary["voice_seconds"] >= 150
    assert summary["voice_minutes"] == seconds_to_billable_minutes(
        summary["voice_seconds"]
    )
    entitlements = entitlements_for_plan("starter")
    assert entitlements is not None
    assert summary["included_minutes"] == entitlements["monthly_minutes"]
    assert summary["overage_minutes"] == 0
    assert summary["resources"]["team_users"]["limit"] == entitlements["team_users"]
    assert summary["period_kind"] == "calendar_month_utc"
