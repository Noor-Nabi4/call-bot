"""Phase 12 Dispatch — status, assignment eligibility, board, history."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from callbot_platform.crm.appointments.technician_availability import (
    TechnicianAvailabilityService,
)
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.dispatch.assignment import DispatchAssignmentService
from callbot_platform.crm.dispatch.board import (
    DispatchBoardService,
    business_day_window,
)
from callbot_platform.crm.dispatch.constants import VALID_TECH_STATUS_TRANSITIONS
from callbot_platform.crm.dispatch.events import list_events_after
from callbot_platform.crm.dispatch.status import TechnicianStatusService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs import JobService
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import TelephonyAuditEvent, Tenant
from callbot_platform.db.models.dispatch import (
    DispatchEvent,
    JobAssignmentHistory,
    TechnicianStatusHistory,
)
from callbot_platform.jobs.repos import JobRepository, TechnicianRepository


def _setup(session: Session, tenant_id: uuid.UUID) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Buyer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="t",
    )
    location = CustomerService(session).locations.create_location(
        tenant_id,
        uuid.UUID(customer["id"]),
        address_line_1="123 Main",
        city="Austin",
        state="TX",
        postal_code="78701",
        actor="t",
    )
    service = ServicesPricebookService(session).create_service(
        tenant_id, name="Repair", actor="t", duration_minutes=60
    )
    tech = TechnicianRepository(session).create(
        tenant_id,
        email=f"tech-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Tech One",
    )
    return {
        "customer_id": uuid.UUID(customer["id"]),
        "location_id": uuid.UUID(location["id"]),
        "service_id": uuid.UUID(service["id"]),
        "technician_id": uuid.UUID(tech["id"]),
    }


def test_business_day_window_timezone() -> None:
    start, end = business_day_window(
        datetime(2026, 6, 15, tzinfo=UTC).date(), "America/Chicago"
    )
    assert (end - start).total_seconds() == 86400
    # Chicago CDT is UTC-5 in June → local midnight = 05:00 UTC
    assert start.hour == 5


def test_technician_status_matrix(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = TechnicianStatusService(session)
    # Created ACTIVE → AVAILABLE
    assert api.get(tenant.id, setup["technician_id"])["status"] == "AVAILABLE"

    path = [
        ("BUSY", True),
        ("EN_ROUTE", True),
        ("ARRIVED", True),
        ("AVAILABLE", True),
        ("OFFLINE", True),
        ("AVAILABLE", True),
        ("ON_BREAK", True),
        ("OFFLINE", True),
        ("BUSY", False),  # OFFLINE → BUSY invalid
    ]
    for status, ok in path:
        if ok:
            api.transition(
                tenant.id,
                setup["technician_id"],
                to_status=status,
                actor="t",
            )
        else:
            with pytest.raises(CrmError) as exc:
                api.transition(
                    tenant.id,
                    setup["technician_id"],
                    to_status=status,
                    actor="t",
                )
            assert exc.value.code == "status_transition_invalid"

    hist = api.history(tenant.id, setup["technician_id"])
    assert len(hist) >= 1
    # Invalid transition must not add history
    before = len(hist)
    with pytest.raises(CrmError):
        api.transition(
            tenant.id,
            setup["technician_id"],
            to_status="BUSY",
            actor="t",
        )
    assert len(api.history(tenant.id, setup["technician_id"])) == before

    # Full matrix completeness
    for src, dst in VALID_TECH_STATUS_TRANSITIONS:
        assert src != dst


def test_assign_unassign_history_and_offline_reject(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    job = JobService(session).create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_type="Repair",
        service_id=setup["service_id"],
        location_id=setup["location_id"],
        scheduled_starts_at=datetime.now(UTC) + timedelta(hours=2),
        scheduled_ends_at=datetime.now(UTC) + timedelta(hours=3),
    )
    jid = uuid.UUID(job["id"])
    assign = DispatchAssignmentService(session)
    result = assign.assign(
        tenant.id,
        jid,
        technician_id=setup["technician_id"],
        actor="disp",
        reason="first",
    )
    assert result["assigned_technician_id"] == str(setup["technician_id"])
    hist = assign.history(tenant.id, jid)
    assert len(hist) == 1
    assert hist[0]["technician_id"] == str(setup["technician_id"])

    assign.assign(tenant.id, jid, technician_id=None, actor="disp", reason="clear")
    hist2 = assign.history(tenant.id, jid)
    assert any(h["technician_id"] is None for h in hist2)

    # Fresh technicians start AVAILABLE; OFFLINE is a valid direct transition.
    TechnicianStatusService(session).transition(
        tenant.id,
        setup["technician_id"],
        to_status="OFFLINE",
        actor="t",
    )
    with pytest.raises(CrmError) as exc:
        assign.assign(
            tenant.id,
            jid,
            technician_id=setup["technician_id"],
            actor="disp",
        )
    assert exc.value.code == "technician_unavailable"


def test_skill_mismatch_blocks_assign(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    avail = TechnicianAvailabilityService(session)
    skill = avail.create_skill(tenant.id, key="hvac", name="HVAC", actor="t")
    avail.set_service_required_skills(
        tenant.id, setup["service_id"], [uuid.UUID(skill["id"])], actor="t"
    )
    job = JobService(session).create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_id=setup["service_id"],
        location_id=setup["location_id"],
        service_type="Repair",
    )
    with pytest.raises(CrmError) as exc:
        DispatchAssignmentService(session).assign(
            tenant.id,
            uuid.UUID(job["id"]),
            technician_id=setup["technician_id"],
            actor="t",
        )
    assert exc.value.code == "skill_mismatch"

    avail.assign_technician_skill(
        tenant.id,
        setup["technician_id"],
        uuid.UUID(skill["id"]),
        actor="t",
    )
    ok = DispatchAssignmentService(session).assign(
        tenant.id,
        uuid.UUID(job["id"]),
        technician_id=setup["technician_id"],
        actor="t",
    )
    assert ok["assigned_technician_id"] == str(setup["technician_id"])


def test_assign_idempotency(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    job = JobService(session).create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_type="X",
    )
    jid = uuid.UUID(job["id"])
    api = DispatchAssignmentService(session)
    a = api.assign(
        tenant.id,
        jid,
        technician_id=setup["technician_id"],
        actor="t",
        idempotency_key="k1",
    )
    b = api.assign(
        tenant.id,
        jid,
        technician_id=setup["technician_id"],
        actor="t",
        idempotency_key="k1",
    )
    assert a["id"] == b["id"]
    count = session.scalar(
        select(JobAssignmentHistory).where(
            JobAssignmentHistory.tenant_id == tenant.id,
            JobAssignmentHistory.idempotency_key == "k1",
        )
    )
    assert count is not None
    with pytest.raises(CrmError) as exc:
        api.assign(
            tenant.id,
            jid,
            technician_id=None,
            actor="t",
            idempotency_key="k1",
        )
    assert exc.value.code == "idempotency_conflict"


def test_board_n_plus_one_bounded(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    tech_ids = [setup["technician_id"]]
    for i in range(14):
        tech = TechnicianRepository(session).create(
            tenant.id,
            email=f"n1-{i}-{uuid.uuid4().hex[:6]}@t.test",
            password="password123",
            name=f"Tech {i}",
        )
        tech_ids.append(uuid.UUID(tech["id"]))
    # Keep jobs inside today's board window (unscheduled pool).
    for i in range(100):
        job = JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            service_type=f"Job {i}",
        )
        if i % 3 == 0:
            DispatchAssignmentService(session).assign(
                tenant.id,
                uuid.UUID(job["id"]),
                technician_id=tech_ids[i % len(tech_ids)],
                actor="t",
            )
    engine: Engine = session.get_bind()
    queries: list[str] = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        board = DispatchBoardService(session).board(tenant.id)
        assert len(board["unassigned_jobs"]) + len(board["assigned_jobs"]) >= 100
        assert len(board["technicians"]) >= 15
    finally:
        event.remove(engine, "before_cursor_execute", _count)
    assert len(queries) < 30, f"too many queries: {len(queries)}"


def test_legacy_job_repo_assign_uses_dispatch_service(
    session: Session, tenant: Tenant
) -> None:
    """Legacy JobRepository.assign must share history/audit/events with CRM path."""
    setup = _setup(session, tenant.id)
    job = JobService(session).create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_type="Legacy",
    )
    jid = uuid.UUID(job["id"])
    legacy = JobRepository(session).assign(
        tenant.id,
        jid,
        technician_id=setup["technician_id"],
        actor="legacy-disp",
    )
    assert legacy["assigned_technician_id"] == str(setup["technician_id"])

    hist = DispatchAssignmentService(session).history(tenant.id, jid)
    assert len(hist) == 1
    assert hist[0]["previous_technician_id"] is None
    assert hist[0]["technician_id"] == str(setup["technician_id"])
    assert hist[0]["changed_by"] == "legacy-disp"

    audits = list(
        session.scalars(
            select(TelephonyAuditEvent).where(
                TelephonyAuditEvent.tenant_id == tenant.id,
                TelephonyAuditEvent.action == "job_assigned",
            )
        ).all()
    )
    assert len(audits) >= 1

    events = list(
        session.scalars(
            select(DispatchEvent).where(
                DispatchEvent.tenant_id == tenant.id,
                DispatchEvent.event_type == "JOB_ASSIGNED",
            )
        ).all()
    )
    assert len(events) >= 1

    # Reassign via CRM path — same history chain.
    tech_b = TechnicianRepository(session).create(
        tenant.id,
        email=f"tb-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Tech B",
    )
    DispatchAssignmentService(session).assign(
        tenant.id,
        jid,
        technician_id=uuid.UUID(tech_b["id"]),
        actor="crm-disp",
        reason="reassign",
    )
    hist2 = DispatchAssignmentService(session).history(tenant.id, jid)
    assert len(hist2) >= 2
    assert any(h["technician_id"] == tech_b["id"] for h in hist2)


def test_dispatch_events_polling_bounded(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    job = JobService(session).create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        service_type="E",
    )
    jid = uuid.UUID(job["id"])
    api = DispatchAssignmentService(session)
    for _ in range(5):
        api.assign(tenant.id, jid, technician_id=setup["technician_id"], actor="t")
        api.assign(tenant.id, jid, technician_id=None, actor="t")
    page = list_events_after(session, tenant.id, limit=3)
    assert len(page) == 3
    after = uuid.UUID(page[-1]["id"])
    page2 = list_events_after(session, tenant.id, after_id=after, limit=500)
    assert len(page2) <= 500
    assert all(e["id"] != page[-1]["id"] for e in page2)


def test_invalid_status_no_audit(session: Session, tenant: Tenant) -> None:
    from sqlalchemy import func

    setup = _setup(session, tenant.id)
    n0 = session.scalar(
        select(func.count())
        .select_from(TelephonyAuditEvent)
        .where(
            TelephonyAuditEvent.tenant_id == tenant.id,
            TelephonyAuditEvent.action == "technician_status_changed",
        )
    )
    with pytest.raises(CrmError):
        TechnicianStatusService(session).transition(
            tenant.id,
            setup["technician_id"],
            to_status="EN_ROUTE",  # AVAILABLE → EN_ROUTE invalid
            actor="t",
        )
    n1 = session.scalar(
        select(func.count())
        .select_from(TelephonyAuditEvent)
        .where(
            TelephonyAuditEvent.tenant_id == tenant.id,
            TelephonyAuditEvent.action == "technician_status_changed",
        )
    )
    assert n1 == n0
    hist_n = session.scalar(
        select(func.count())
        .select_from(TechnicianStatusHistory)
        .where(TechnicianStatusHistory.technician_id == setup["technician_id"])
    )
    assert hist_n == 0
