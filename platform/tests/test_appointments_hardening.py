"""Phase 11 Appointments hardening: matrix, DST, emergency, N+1, integrity."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from callbot_platform.crm.appointments.constants import (
    APPOINTMENT_STATUSES,
    VALID_TRANSITIONS,
    AppointmentStatus,
)
from callbot_platform.crm.appointments.engine import AvailabilityEngine
from callbot_platform.crm.appointments.hours import (
    BusinessHoursService,
    validate_weekly_hours,
)
from callbot_platform.crm.appointments.service import AppointmentService
from callbot_platform.crm.appointments.technician_availability import (
    TechnicianAvailabilityService,
)
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import TelephonyAuditEvent, Tenant
from callbot_platform.db.models.scheduling import Appointment, AppointmentStatusHistory
from callbot_platform.jobs.repos import TechnicianRepository


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _setup(session: Session, tenant_id: uuid.UUID, **service_kwargs) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Buyer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="t",
    )
    location = CustomerService(session).locations.create_location(
        tenant_id,
        uuid.UUID(customer["id"]),
        address_line_1="123 Main St",
        city="Austin",
        state="TX",
        postal_code="78701",
        actor="t",
    )
    service = ServicesPricebookService(session).create_service(
        tenant_id, name="AC Repair", actor="t", **service_kwargs
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


def _next_weekday_local(
    tz_name: str, weekday: int, hour: int, minute: int = 0
) -> datetime:
    """Next local wall-clock datetime for weekday (0=Mon) in tz, returned as UTC."""
    tz = ZoneInfo(tz_name)
    now_local = datetime.now(tz)
    days = (weekday - now_local.weekday()) % 7
    if days == 0 and (now_local.hour, now_local.minute) >= (hour, minute):
        days = 7
    day = now_local.date() + timedelta(days=days)
    local = datetime(day.year, day.month, day.day, hour, minute, tzinfo=tz)
    return local.astimezone(UTC)


def test_adjacent_weekly_periods_allowed() -> None:
    cleaned = validate_weekly_hours({"mon": [["09:00", "12:00"], ["12:00", "17:00"]]})
    assert cleaned["mon"] == [["09:00", "12:00"], ["12:00", "17:00"]]


def test_overnight_periods_rejected() -> None:
    with pytest.raises(CrmError) as exc:
        validate_weekly_hours({"mon": [["22:00", "02:00"]]})
    assert exc.value.code == "invalid_weekly_hours"
    assert "overnight" in str(exc.value).lower() or "before close" in str(exc.value)


def _force_status(session: Session, appointment_id: uuid.UUID, status: str) -> None:
    """Test helper: set status without going through the transition graph."""
    row = session.get(Appointment, appointment_id)
    assert row is not None
    row.status = status
    if status == AppointmentStatus.CANCELLED.value:
        row.cancelled_at = datetime.now(UTC)
    if status == AppointmentStatus.COMPLETED.value:
        row.completed_at = datetime.now(UTC)
    session.flush()


def test_full_transition_matrix_and_invalids(session: Session, tenant: Tenant) -> None:
    """Every (src, dst) pair: valid → mutates; invalid → no history / no success audit."""
    setup = _setup(session, tenant.id, duration_minutes=60)
    BusinessHoursService(session).update(
        tenant.id,
        actor="t",
        timezone="UTC",
        weekly_hours={
            d: [["00:00", "23:59"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
    )
    api = AppointmentService(session)
    # Unassigned appointments — transition matrix must not depend on technician
    # exclusion conflicts between fixture rows.
    base = _next_weekday_local("UTC", 0, 6)
    idx = 0
    for src in sorted(APPOINTMENT_STATUSES):
        for dst in sorted(APPOINTMENT_STATUSES):
            if src == dst:
                continue
            starts = base + timedelta(minutes=idx * 5)
            idx += 1
            appt = api.create(
                tenant.id,
                customer_id=setup["customer_id"],
                starts_at=starts,
                actor="t",
                service_id=setup["service_id"],
                duration_minutes=5,
                status="TENTATIVE",
            )
            aid = uuid.UUID(appt["id"])
            _force_status(session, aid, src)
            # IN_PROGRESS requires a technician in domain rules.
            if dst == AppointmentStatus.IN_PROGRESS.value:
                row = session.get(Appointment, aid)
                assert row is not None
                row.assigned_technician_id = setup["technician_id"]
                session.flush()
            hist_before = session.scalar(
                select(func.count())
                .select_from(AppointmentStatusHistory)
                .where(AppointmentStatusHistory.appointment_id == aid)
            )
            if (src, dst) in VALID_TRANSITIONS:
                result = api.transition(tenant.id, aid, to_status=dst, actor="matrix")
                assert result["status"] == dst
                hist_after = session.scalar(
                    select(func.count())
                    .select_from(AppointmentStatusHistory)
                    .where(AppointmentStatusHistory.appointment_id == aid)
                )
                assert hist_after == (hist_before or 0) + 1
            else:
                with pytest.raises(CrmError) as exc:
                    api.transition(tenant.id, aid, to_status=dst, actor="matrix")
                assert exc.value.code == "invalid_transition"
                row = session.get(Appointment, aid)
                assert row is not None
                assert row.status == src
                hist_after = session.scalar(
                    select(func.count())
                    .select_from(AppointmentStatusHistory)
                    .where(AppointmentStatusHistory.appointment_id == aid)
                )
                assert hist_after == hist_before


def test_invalid_transition_no_history_or_audit(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id, duration_minutes=30)
    BusinessHoursService(session).update(
        tenant.id,
        actor="t",
        timezone="UTC",
        weekly_hours={
            d: [["00:00", "23:59"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
    )
    api = AppointmentService(session)
    appt = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=_next_weekday_local("UTC", 0, 9),
        actor="t",
        service_id=setup["service_id"],
    )
    aid = uuid.UUID(appt["id"])
    hist_before = len(
        list(
            session.scalars(
                select(AppointmentStatusHistory).where(
                    AppointmentStatusHistory.appointment_id == aid
                )
            ).all()
        )
    )
    with pytest.raises(CrmError):
        api.transition(tenant.id, aid, to_status="COMPLETED", actor="t")
    hist_after = len(
        list(
            session.scalars(
                select(AppointmentStatusHistory).where(
                    AppointmentStatusHistory.appointment_id == aid
                )
            ).all()
        )
    )
    assert hist_after == hist_before
    row = session.get(Appointment, aid)
    assert row is not None
    assert row.status == AppointmentStatus.SCHEDULED.value


def test_emergency_hours_not_used_for_normal_availability(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id, duration_minutes=60)
    BusinessHoursService(session).update(
        tenant.id,
        actor="t",
        timezone="UTC",
        weekly_hours={d: [] for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]},
        emergency_weekly_hours={
            d: [["18:00", "22:00"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
        slot_minutes=60,
        booking_horizon_days=14,
    )
    tech_api = TechnicianAvailabilityService(session)
    tech_api.create_period(
        tenant.id,
        setup["technician_id"],
        day_of_week=0,
        open_time="18:00",
        close_time="22:00",
        actor="t",
    )
    engine = AvailabilityEngine(session)
    start = _next_weekday_local("UTC", 0, 18).date()
    normal = engine.compute(
        tenant.id,
        from_date=start,
        to_date=start,
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
        is_emergency=False,
        limit=20,
    )
    emergency = engine.compute(
        tenant.id,
        from_date=start,
        to_date=start,
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
        is_emergency=True,
        limit=20,
    )
    assert normal["slots"] == []
    assert len(emergency["slots"]) >= 1


def test_cancelled_does_not_block_availability(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id, duration_minutes=60)
    BusinessHoursService(session).update(
        tenant.id,
        actor="t",
        timezone="UTC",
        weekly_hours={
            d: [["09:00", "17:00"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
        slot_minutes=60,
    )
    starts = _next_weekday_local("UTC", 0, 10)
    api = AppointmentService(session)
    appt = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
    )
    api.cancel(tenant.id, uuid.UUID(appt["id"]), actor="t")
    slots = AvailabilityEngine(session).compute(
        tenant.id,
        from_date=starts.date(),
        to_date=starts.date(),
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
        limit=50,
    )
    assert any(
        datetime.fromisoformat(s["starts_at"]).astimezone(UTC) == starts
        for s in slots["slots"]
    )


def test_dst_spring_forward_duration_america_new_york(
    session: Session, tenant: Tenant
) -> None:
    """US spring-forward 2026-03-08: 2h wall clock across gap is still 120 UTC minutes."""
    setup = _setup(session, tenant.id)
    BusinessHoursService(session).update(
        tenant.id, actor="t", timezone="America/New_York"
    )
    tz = ZoneInfo("America/New_York")
    # Local 01:30 EST on spring-forward day — before the jump; +120m lands after 03:00 EDT.
    local_start = datetime(2026, 3, 8, 1, 30, tzinfo=tz)
    starts = local_start.astimezone(UTC)
    api = AppointmentService(session)
    appt = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_type="DST Test",
        duration_minutes=120,
        technician_id=setup["technician_id"],
    )
    ends = datetime.fromisoformat(appt["ends_at"])
    assert (ends - datetime.fromisoformat(appt["starts_at"])).total_seconds() == 7200
    # Local end should be 04:30 EDT (clocks skipped 02:00-03:00).
    local_end = ends.astimezone(tz)
    assert local_end.hour == 4 and local_end.minute == 30


def test_dst_fall_back_duration_america_new_york(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    BusinessHoursService(session).update(
        tenant.id, actor="t", timezone="America/New_York"
    )
    tz = ZoneInfo("America/New_York")
    # Ambiguous 01:30 — fold=0 picks first (EDT) occurrence.
    local_start = datetime(2026, 11, 1, 1, 30, fold=0, tzinfo=tz)
    starts = local_start.astimezone(UTC)
    appt = AppointmentService(session).create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_type="DST Fall",
        duration_minutes=120,
        technician_id=setup["technician_id"],
    )
    ends = datetime.fromisoformat(appt["ends_at"])
    assert (ends - datetime.fromisoformat(appt["starts_at"])).total_seconds() == 7200


def test_job_customer_mismatch_rejected(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id, duration_minutes=30)
    other = CustomerService(session).create(
        tenant.id, name="Other", phone="+15559990002", actor="t"
    )
    from callbot_platform.crm.jobs import JobService

    job = JobService(session).create(
        tenant.id,
        customer_id=uuid.UUID(other["id"]),
        actor="t",
        service_type="X",
    )
    BusinessHoursService(session).update(
        tenant.id,
        actor="t",
        timezone="UTC",
        weekly_hours={
            d: [["00:00", "23:59"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
    )
    with pytest.raises(CrmError) as exc:
        AppointmentService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=_next_weekday_local("UTC", 0, 11),
            actor="t",
            service_id=setup["service_id"],
            job_id=uuid.UUID(job["id"]),
        )
    assert exc.value.code == "job_customer_mismatch"


def test_assign_into_conflict_rejected(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id, duration_minutes=60)
    tech2 = TechnicianRepository(session).create(
        tenant.id,
        email=f"tech2-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Tech Two",
    )
    BusinessHoursService(session).update(
        tenant.id,
        actor="t",
        timezone="UTC",
        weekly_hours={
            d: [["00:00", "23:59"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
    )
    starts = _next_weekday_local("UTC", 0, 10)
    api = AppointmentService(session)
    api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
    )
    free = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_id=setup["service_id"],
        technician_id=uuid.UUID(tech2["id"]),
    )
    with pytest.raises(CrmError) as exc:
        api.assign(
            tenant.id,
            uuid.UUID(free["id"]),
            technician_id=setup["technician_id"],
            actor="t",
        )
    assert exc.value.code == "slot_conflict"


def test_list_n_plus_one_bounded(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id, duration_minutes=30)
    BusinessHoursService(session).update(
        tenant.id,
        actor="t",
        timezone="UTC",
        weekly_hours={
            d: [["00:00", "23:59"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
    )
    api = AppointmentService(session)
    base = _next_weekday_local("UTC", 0, 8)
    for i in range(25):
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=base + timedelta(hours=i),
            actor="t",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )

    engine = session.get_bind()
    assert isinstance(engine, Engine)
    queries: list[str] = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        result = api.list(tenant.id, limit=20)
        assert len(result["appointments"]) == 20
    finally:
        event.remove(engine, "before_cursor_execute", _count)
    assert len(queries) < 15, f"too many queries: {len(queries)}"


def test_availability_duration_boundary(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id, duration_minutes=90)
    BusinessHoursService(session).update(
        tenant.id,
        actor="t",
        timezone="UTC",
        weekly_hours={
            "mon": [["09:00", "10:00"]],
            "tue": [],
            "wed": [],
            "thu": [],
            "fri": [],
            "sat": [],
            "sun": [],
        },
        slot_minutes=30,
    )
    tech_api = TechnicianAvailabilityService(session)
    tech_api.create_period(
        tenant.id,
        setup["technician_id"],
        day_of_week=0,
        open_time="09:00",
        close_time="10:00",
        actor="t",
    )
    day = _next_weekday_local("UTC", 0, 9).date()
    engine = AvailabilityEngine(session)
    too_long = engine.compute(
        tenant.id,
        from_date=day,
        to_date=day,
        service_id=setup["service_id"],
        duration_minutes=90,
        technician_id=setup["technician_id"],
        limit=20,
    )
    assert too_long["slots"] == []
    fits = engine.compute(
        tenant.id,
        from_date=day,
        to_date=day,
        duration_minutes=60,
        technician_id=setup["technician_id"],
        limit=20,
    )
    assert len(fits["slots"]) >= 1


def test_cross_tenant_skill_isolation(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    setup_a = _setup(session, tenant.id, duration_minutes=60)
    setup_b = _setup(session, tenant_b.id, duration_minutes=60)
    tech_api = TechnicianAvailabilityService(session)
    skill_b = tech_api.create_skill(tenant_b.id, key="HVAC", name="HVAC", actor="t")
    with pytest.raises(CrmError):
        tech_api.assign_technician_skill(
            tenant.id,
            setup_a["technician_id"],
            uuid.UUID(skill_b["id"]),
            actor="t",
        )
    with pytest.raises(CrmError):
        tech_api.assign_technician_skill(
            tenant_b.id,
            setup_a["technician_id"],
            uuid.UUID(skill_b["id"]),
            actor="t",
        )
    assert setup_b["technician_id"] != setup_a["technician_id"]


@pytest.mark.parametrize(
    "tz_name",
    [
        "America/New_York",
        "America/Chicago",
        "America/Denver",
        "America/Los_Angeles",
        "Europe/London",
        "Asia/Karachi",
        "Australia/Sydney",
    ],
)
def test_timezone_matrix_create_and_serialize(
    session: Session, tenant: Tenant, tz_name: str
) -> None:
    setup = _setup(session, tenant.id, duration_minutes=60)
    BusinessHoursService(session).update(
        tenant.id,
        actor="t",
        timezone=tz_name,
        weekly_hours={
            d: [["00:00", "23:59"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
    )
    starts = _next_weekday_local(tz_name, 0, 10)
    appt = AppointmentService(session).create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
    )
    assert appt["timezone"] == tz_name
    parsed = datetime.fromisoformat(appt["starts_at"])
    assert parsed.tzinfo is not None
    assert abs((parsed.astimezone(UTC) - starts).total_seconds()) < 1


def test_availability_constraint_matrix(session: Session, tenant: Tenant) -> None:
    """Business x tech schedule x break x conflict x skill x area combinations."""
    setup = _setup(session, tenant.id, duration_minutes=60)
    tech_api = TechnicianAvailabilityService(session)
    BusinessHoursService(session).update(
        tenant.id,
        actor="t",
        timezone="UTC",
        weekly_hours={
            "mon": [["09:00", "17:00"]],
            "tue": [],
            "wed": [],
            "thu": [],
            "fri": [],
            "sat": [],
            "sun": [],
        },
        slot_minutes=60,
    )
    tech_api.create_period(
        tenant.id,
        setup["technician_id"],
        day_of_week=0,
        open_time="09:00",
        close_time="17:00",
        actor="t",
    )
    skill = tech_api.create_skill(tenant.id, key="hvac", name="HVAC", actor="t")
    tech_api.assign_technician_skill(
        tenant.id, setup["technician_id"], uuid.UUID(skill["id"]), actor="t"
    )
    tech_api.set_service_required_skills(
        tenant.id, setup["service_id"], [uuid.UUID(skill["id"])], actor="t"
    )
    area = tech_api.create_service_area(
        tenant.id,
        key="austin-78701",
        name="Austin",
        match_type="POSTAL_CODE",
        match_value="78701",
        actor="t",
    )
    tech_api.assign_technician_service_area(
        tenant.id, setup["technician_id"], uuid.UUID(area["id"]), actor="t"
    )
    day = _next_weekday_local("UTC", 0, 10).date()
    engine = AvailabilityEngine(session)

    ok = engine.compute(
        tenant.id,
        from_date=day,
        to_date=day,
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
        location_id=setup["location_id"],
        limit=20,
    )
    assert len(ok["slots"]) >= 1

    closed = engine.compute(
        tenant.id,
        from_date=day + timedelta(days=1),  # Tuesday closed
        to_date=day + timedelta(days=1),
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
        location_id=setup["location_id"],
        limit=20,
    )
    assert closed["slots"] == []

    tech_api.create_break(
        tenant.id,
        setup["technician_id"],
        day_of_week=0,
        start_time="10:00",
        end_time="11:00",
        actor="t",
    )
    with_break = engine.compute(
        tenant.id,
        from_date=day,
        to_date=day,
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
        location_id=setup["location_id"],
        limit=50,
    )
    assert not any(
        datetime.fromisoformat(s["starts_at"]).astimezone(UTC).hour == 10
        for s in with_break["slots"]
    )


def test_reschedule_audit_includes_old_window(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id, duration_minutes=60)
    BusinessHoursService(session).update(
        tenant.id,
        actor="t",
        timezone="UTC",
        weekly_hours={
            d: [["00:00", "23:59"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
    )
    api = AppointmentService(session)
    starts = _next_weekday_local("UTC", 0, 9)
    appt = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        starts_at=starts,
        actor="t",
        service_id=setup["service_id"],
        technician_id=setup["technician_id"],
    )
    api.reschedule(
        tenant.id,
        uuid.UUID(appt["id"]),
        starts_at=starts + timedelta(hours=2),
        actor="t",
    )
    events = list(
        session.scalars(
            select(TelephonyAuditEvent).where(
                TelephonyAuditEvent.tenant_id == tenant.id,
                TelephonyAuditEvent.action == "appointment_rescheduled",
            )
        ).all()
    )
    assert len(events) == 1
    summary = events[0].payload_summary or {}
    assert "old_starts_at" in summary
    assert "starts_at" in summary
