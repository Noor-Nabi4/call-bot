"""Phase 27 analytics range + aggregation tests."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

from sqlalchemy.orm import Session

from callbot_platform.analytics.range import AnalyticsRangeError, build_range
from callbot_platform.analytics.service import AnalyticsService
from callbot_platform.crm.repos import CallRepository
from callbot_platform.db.models import Call, Job, Lead, Tenant


def test_build_range_today_tenant_local() -> None:
    rng = build_range(
        timezone="America/New_York",
        preset="today",
        now=datetime(2026, 6, 15, 16, 30, tzinfo=UTC),  # 12:30 PM EDT
    )
    assert rng.local_from_date == date(2026, 6, 15)
    assert rng.local_to_date == date(2026, 6, 15)
    assert rng.starts_from < rng.starts_to
    # Half-open: ends at next local midnight in UTC
    assert rng.starts_to.astimezone(UTC).hour in {4, 5}  # EDT/EST midnight→UTC


def test_build_range_last_7_days_inclusive() -> None:
    rng = build_range(
        timezone="UTC",
        preset="last_7_days",
        now=datetime(2026, 6, 15, 12, 0, tzinfo=UTC),
    )
    assert rng.local_from_date == date(2026, 6, 9)
    assert rng.local_to_date == date(2026, 6, 15)


def test_build_range_rejects_bad_custom() -> None:
    try:
        build_range(
            timezone="UTC",
            preset="custom",
            from_date=date(2026, 6, 10),
            to_date=date(2026, 6, 1),
        )
        raise AssertionError("expected error")
    except AnalyticsRangeError as exc:
        assert exc.code == "invalid_custom_range"


def test_analytics_calls_empty_and_ai_resolution(
    session: Session, tenant: Tenant
) -> None:
    svc = AnalyticsService(session)
    out = svc.calls_section(tenant.id, preset="last_30_days")
    assert out["calls"]["total"] == 0
    assert out["calls"]["answer_rate"] is None
    assert out["calls"]["missed"] is None
    assert out["calls"]["ai_resolution_rate"] is None
    assert out["calls"]["transfer_rate"] is None
    assert "range" in out

    repo = CallRepository(session)
    started = repo.start(tenant.id, room_name="a1", caller_number="+15551110001")
    call_id = uuid.UUID(started["id"])
    row = session.get(Call, call_id)
    assert row is not None
    row.started_at = datetime.now(UTC) - timedelta(seconds=90)
    session.flush()
    repo.end(
        tenant.id,
        call_id=call_id,
        status="closed",
        metrics={"handoff_requested": False},
    )

    started2 = repo.start(tenant.id, room_name="a2", caller_number="+15551110002")
    call_id2 = uuid.UUID(started2["id"])
    row2 = session.get(Call, call_id2)
    assert row2 is not None
    row2.started_at = datetime.now(UTC) - timedelta(seconds=60)
    session.flush()
    repo.end(
        tenant.id,
        call_id=call_id2,
        status="closed",
        metrics={"handoff_requested": True, "transfer_kind": "warm"},
    )

    # Disposition-based answer/missed
    row.disposition_code = "resolved"
    row2.disposition_code = "no_answer"
    session.flush()

    out2 = svc.calls_section(tenant.id, preset="last_30_days")
    calls = out2["calls"]
    assert calls["total"] >= 2
    assert calls["ended"] >= 2
    assert calls["answer_rate"] is not None
    assert calls["missed"] == 1
    assert calls["transfer_rate"] is not None
    assert calls["transfers"] >= 1
    assert calls["ai_resolution_rate"] is not None
    assert 0.0 <= float(calls["ai_resolution_rate"]) <= 1.0
    assert isinstance(calls["calls_by_day"], list)


def test_analytics_sales_leads_and_unavailable_attribution(
    session: Session, tenant: Tenant
) -> None:
    session.add(
        Lead(
            tenant_id=tenant.id,
            title="Lead A",
            status="QUALIFIED",
            source="PHONE",
            priority="MEDIUM",
            reference_code="LD-AAA111",
        )
    )
    session.add(
        Lead(
            tenant_id=tenant.id,
            title="Lead B",
            status="NEW",
            source="WEBSITE",
            priority="LOW",
            reference_code="LD-BBB222",
        )
    )
    session.flush()

    sales = AnalyticsService(session).sales_section(tenant.id, preset="last_30_days")[
        "sales"
    ]
    assert sales["leads"] >= 2
    assert sales["qualified_leads"] >= 1
    assert sales["revenue_per_lead"] is None
    assert sales["revenue_per_call"] is None
    assert "revenue_per_lead_unavailable" in sales
    assert sales["product_sales"] == 0.0


def test_analytics_operations_completed_and_utilization_null(
    session: Session, tenant: Tenant
) -> None:
    from callbot_platform.db.models import Customer

    cust = Customer(tenant_id=tenant.id, name="Ops Cust")
    session.add(cust)
    session.flush()
    session.add(
        Job(
            tenant_id=tenant.id,
            customer_id=cust.id,
            job_number="JOB-OPS-001",
            status="COMPLETED",
            priority="MEDIUM",
            service_type="Repair",
            reference_code="REF-OPS-1",
            completed_at=datetime.now(UTC),
            scheduled_starts_at=datetime.now(UTC) - timedelta(hours=2),
            scheduled_ends_at=datetime.now(UTC) - timedelta(hours=1),
        )
    )
    session.add(
        Job(
            tenant_id=tenant.id,
            customer_id=cust.id,
            job_number="JOB-OPS-002",
            status="CANCELLED",
            priority="MEDIUM",
            service_type="Repair",
            reference_code="REF-OPS-2",
            cancelled_at=datetime.now(UTC),
        )
    )
    session.flush()

    ops = AnalyticsService(session).operations_section(
        tenant.id, preset="last_30_days"
    )["operations"]
    assert ops["jobs_completed"] >= 1
    assert ops["cancellation_rate"] is not None
    assert ops["technician_utilization"] is None
    assert ops["technician_utilization_unavailable"]
    assert ops["average_job_duration_seconds"] is not None


def test_analytics_tenant_isolation(session: Session, tenant: Tenant) -> None:
    other = Tenant(
        name="Other",
        slug=f"other-{uuid.uuid4().hex[:8]}",
        timezone="UTC",
    )
    # Minimal required fields for Tenant vary — use factory if insert fails
    for attr, val in (
        ("currency", "USD"),
        ("db_strategy", "shared"),
    ):
        if hasattr(other, attr):
            setattr(other, attr, val)
    session.add(other)
    session.flush()

    session.add(
        Lead(
            tenant_id=other.id,
            title="Other lead",
            status="NEW",
            source="OTHER",
            priority="LOW",
            reference_code="LD-OTHER1",
        )
    )
    session.flush()

    overview = AnalyticsService(session).overview(tenant.id, preset="last_7_days")
    assert "calls" in overview and "sales" in overview and "operations" in overview
    other_sales = AnalyticsService(session).sales_section(
        other.id, preset="last_30_days"
    )["sales"]
    assert other_sales["leads"] == 1
    own_sales = AnalyticsService(session).sales_section(
        tenant.id, preset="last_30_days"
    )["sales"]
    assert own_sales["leads"] == 0
