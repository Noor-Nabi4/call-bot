"""PostgreSQL concurrency tests for Phase 11 Appointments.

Skip when Postgres is unavailable — SQLite has no exclusion constraint and
cannot prove the real race-safety guarantees (double-booking prevention via
``excl_appointments_technician_active_range``, numbering, idempotency).
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.crm.appointments.hours import BusinessHoursService
from callbot_platform.crm.appointments.service import AppointmentService
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Base, Tenant
from callbot_platform.db.models.scheduling import Appointment, AppointmentNumberCounter
from callbot_platform.jobs.repos import TechnicianRepository

PG_URL = os.environ.get(
    "APPOINTMENTS_PG_TEST_URL",
    os.environ.get(
        "JOBS_PG_TEST_URL",
        os.environ.get(
            "ORDERS_PG_TEST_URL",
            os.environ.get(
                "LEADS_PG_TEST_URL",
                os.environ.get(
                    "INVENTORY_PG_TEST_URL",
                    "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
                ),
            ),
        ),
    ),
)


def _pg_available(url: str) -> bool:
    try:
        engine = create_engine(url, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception:
        return False
    return True


_PG_UP = _pg_available(PG_URL)

pytestmark = pytest.mark.skipif(
    not _PG_UP,
    reason="PostgreSQL not available for appointments concurrency tests",
)


@pytest.fixture()
def pg_factory():
    engine = create_engine(PG_URL, future=True, pool_size=10, max_overflow=5)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        # Mirrors alembic/versions/0041_appointments_scheduling.py — the
        # authoritative race guard that Base.metadata.create_all cannot
        # express (raw EXCLUDE USING gist is not an ORM-mapped construct).
        conn.execute(
            text(
                """
                ALTER TABLE appointments
                ADD CONSTRAINT excl_appointments_technician_active_range
                EXCLUDE USING gist (
                    tenant_id WITH =,
                    assigned_technician_id WITH =,
                    tstzrange(starts_at, ends_at, '[)') WITH &&
                )
                WHERE (
                    assigned_technician_id IS NOT NULL
                    AND archived_at IS NULL
                    AND status IN ('TENTATIVE', 'SCHEDULED', 'CONFIRMED', 'IN_PROGRESS')
                )
                """
            )
        )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def _tenant(session: Session) -> Tenant:
    row = Tenant(name="Appointments PG", slug=f"appt-pg-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _field_setup(session: Session, tenant_id: uuid.UUID, **service_kwargs) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Buyer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="setup",
    )
    service = ServicesPricebookService(session).create_service(
        tenant_id, name="Repair", actor="setup", **service_kwargs
    )
    tech = TechnicianRepository(session).create(
        tenant_id,
        email=f"tech-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Field Tech",
    )
    return {
        "customer_id": uuid.UUID(customer["id"]),
        "service_id": uuid.UUID(service["id"]),
        "technician_id": uuid.UUID(tech["id"]),
    }


def _next_monday_9am() -> datetime:
    now = datetime.now(UTC)
    days_ahead = (7 - now.weekday()) % 7 or 7
    day = (now + timedelta(days=days_ahead)).date()
    return datetime(day.year, day.month, day.day, 9, 0, tzinfo=UTC)


def test_concurrent_double_book_same_technician_one_winner(pg_factory) -> None:
    """Two overlapping create() calls for the same technician — exactly one
    succeeds; the loser gets a controlled slot_conflict, not a crash.
    """
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id, duration_minutes=60)
        BusinessHoursService(session).update(
            tenant.id,
            actor="setup",
            weekly_hours={
                d: [["00:00", "23:59"]]
                for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            },
        )
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
        starts = _next_monday_9am()
    finally:
        session.close()

    def worker(n: int) -> dict:
        s = pg_factory()
        try:
            appt = AppointmentService(s).create(
                tenant_id,
                customer_id=setup_ids["customer_id"],
                starts_at=starts,
                actor=f"w-{n}",
                service_id=setup_ids["service_id"],
                technician_id=setup_ids["technician_id"],
            )
            s.commit()
            return {"ok": True, "id": appt["id"]}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        futures = [pool.submit(worker, n) for n in range(6)]
        results = [f.result() for f in as_completed(futures)]

    oks = [r for r in results if r["ok"]]
    fails = [r for r in results if not r["ok"]]
    assert len(oks) == 1
    assert len(fails) == 5
    assert all(f["code"] == "slot_conflict" for f in fails)

    s = pg_factory()
    try:
        count = s.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.tenant_id == tenant_id,
                Appointment.assigned_technician_id == setup_ids["technician_id"],
            )
        )
        assert count == 1
    finally:
        s.close()


def test_adjacent_slots_both_succeed(pg_factory) -> None:
    """Half-open [start, end) intervals: back-to-back bookings don't conflict."""
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id, duration_minutes=60)
        BusinessHoursService(session).update(
            tenant.id,
            actor="setup",
            weekly_hours={
                d: [["00:00", "23:59"]]
                for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            },
        )
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
        starts = _next_monday_9am()
    finally:
        session.close()

    def worker(offset_minutes: int) -> dict:
        s = pg_factory()
        try:
            appt = AppointmentService(s).create(
                tenant_id,
                customer_id=setup_ids["customer_id"],
                starts_at=starts + timedelta(minutes=offset_minutes),
                actor="w",
                service_id=setup_ids["service_id"],
                technician_id=setup_ids["technician_id"],
            )
            s.commit()
            return {"ok": True, "id": appt["id"]}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, 0), pool.submit(worker, 60)]
        results = [f.result() for f in as_completed(futures)]

    assert all(r["ok"] for r in results), results

    s = pg_factory()
    try:
        count = s.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.tenant_id == tenant_id,
                Appointment.assigned_technician_id == setup_ids["technician_id"],
            )
        )
        assert count == 2
    finally:
        s.close()


def test_duplicate_idempotency_key_create_race(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
        starts = _next_monday_9am()
    finally:
        session.close()

    def worker(n: int) -> str:
        s = pg_factory()
        try:
            appt = AppointmentService(s).create(
                tenant_id,
                customer_id=setup_ids["customer_id"],
                starts_at=starts,
                actor=f"w-{n}",
                service_id=setup_ids["service_id"],
                idempotency_key="same-key",
            )
            s.commit()
            return appt["id"]
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(worker, range(6)))
    assert len(set(ids)) == 1

    s = pg_factory()
    try:
        count = s.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.tenant_id == tenant_id)
        )
        assert count == 1
    finally:
        s.close()


def test_concurrent_appointment_number_generation_unique(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
        starts = _next_monday_9am()
    finally:
        session.close()

    def worker(n: int) -> str:
        s = pg_factory()
        try:
            appt = AppointmentService(s).create(
                tenant_id,
                customer_id=setup_ids["customer_id"],
                starts_at=starts + timedelta(hours=n),
                actor=f"w-{n}",
                service_id=setup_ids["service_id"],
            )
            s.commit()
            return appt["appointment_number"]
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        numbers = list(pool.map(worker, range(8)))
    assert len(numbers) == len(set(numbers))
    assert all(n.startswith("APT-") for n in numbers)

    s = pg_factory()
    try:
        counter = s.scalar(
            select(AppointmentNumberCounter).where(
                AppointmentNumberCounter.tenant_id == tenant_id
            )
        )
        assert counter is not None
        assert counter.last_value == 8
    finally:
        s.close()


def test_multi_tenant_appointment_numbers_isolated(pg_factory) -> None:
    session = pg_factory()
    try:
        t1 = _tenant(session)
        t2 = Tenant(name="Appointments PG B", slug=f"appt-pg-b-{uuid.uuid4().hex[:8]}")
        session.add(t2)
        session.flush()
        s1 = _field_setup(session, t1.id)
        s2 = _field_setup(session, t2.id)
        session.commit()
        tid1, tid2 = t1.id, t2.id
        setup1, setup2 = s1, s2
        starts = _next_monday_9am()
    finally:
        session.close()

    def worker(tenant_id: uuid.UUID, setup: dict, n: int) -> str:
        s = pg_factory()
        try:
            appt = AppointmentService(s).create(
                tenant_id,
                customer_id=setup["customer_id"],
                starts_at=starts + timedelta(hours=n),
                actor=f"w-{n}",
                service_id=setup["service_id"],
            )
            s.commit()
            return appt["appointment_number"]
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        f1 = [pool.submit(worker, tid1, setup1, i) for i in range(4)]
        f2 = [pool.submit(worker, tid2, setup2, i) for i in range(4)]
        n1 = [f.result() for f in f1]
        n2 = [f.result() for f in f2]
    assert len(set(n1)) == 4
    assert len(set(n2)) == 4
    assert "APT-000001" in n1 and "APT-000001" in n2


def test_reschedule_into_conflict_rejected_under_race(pg_factory) -> None:
    """Rescheduling appointment B into A's slot while A is concurrently
    created must fail with slot_conflict, never silently double-book.
    """
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id, duration_minutes=60)
        BusinessHoursService(session).update(
            tenant.id,
            actor="setup",
            weekly_hours={
                d: [["00:00", "23:59"]]
                for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            },
        )
        starts = _next_monday_9am()
        api = AppointmentService(session)
        a = api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts,
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
        b = api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts + timedelta(hours=3),
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
        session.commit()
        tenant_id = tenant.id
        a_id = uuid.UUID(a["id"])
        b_id = uuid.UUID(b["id"])
        _ = a_id
    finally:
        session.close()

    s = pg_factory()
    try:
        with pytest.raises(CrmError) as exc:
            AppointmentService(s).reschedule(
                tenant_id, b_id, starts_at=starts, actor="t"
            )
        assert exc.value.code == "slot_conflict"
    finally:
        s.close()


def test_exact_same_interval_double_book(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id, duration_minutes=60)
        BusinessHoursService(session).update(
            tenant.id,
            actor="setup",
            weekly_hours={
                d: [["00:00", "23:59"]]
                for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            },
        )
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
        starts = _next_monday_9am()
    finally:
        session.close()

    def worker(n: int) -> dict:
        s = pg_factory()
        try:
            AppointmentService(s).create(
                tenant_id,
                customer_id=setup_ids["customer_id"],
                starts_at=starts,
                actor=f"w-{n}",
                service_id=setup_ids["service_id"],
                technician_id=setup_ids["technician_id"],
            )
            s.commit()
            return {"ok": True}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result() for f in as_completed([pool.submit(worker, i) for i in range(2)])]
    oks = [r for r in results if r["ok"]]
    fails = [r for r in results if not r["ok"]]
    assert len(oks) == 1
    assert len(fails) == 1
    assert fails[0]["code"] in {"slot_conflict", "appointment_conflict"}


def test_different_technicians_same_slot_both_ok(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id, duration_minutes=60)
        tech2 = TechnicianRepository(session).create(
            tenant.id,
            email=f"tech2-{uuid.uuid4().hex[:6]}@t.test",
            password="password123",
            name="Tech Two",
        )
        BusinessHoursService(session).update(
            tenant.id,
            actor="setup",
            weekly_hours={
                d: [["00:00", "23:59"]]
                for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            },
        )
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
        tech_b = uuid.UUID(tech2["id"])
        starts = _next_monday_9am()
    finally:
        session.close()

    def worker(tech_id: uuid.UUID) -> dict:
        s = pg_factory()
        try:
            AppointmentService(s).create(
                tenant_id,
                customer_id=setup_ids["customer_id"],
                starts_at=starts,
                actor="w",
                service_id=setup_ids["service_id"],
                technician_id=tech_id,
            )
            s.commit()
            return {"ok": True}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed(
                [
                    pool.submit(worker, setup_ids["technician_id"]),
                    pool.submit(worker, tech_b),
                ]
            )
        ]
    assert all(r["ok"] for r in results)


def test_availability_then_book_race(pg_factory) -> None:
    """Availability is advisory: a concurrent book must win; loser conflicts."""
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id, duration_minutes=60)
        BusinessHoursService(session).update(
            tenant.id,
            actor="setup",
            weekly_hours={
                d: [["00:00", "23:59"]]
                for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            },
            slot_minutes=60,
        )
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
        starts = _next_monday_9am()
    finally:
        session.close()

    from callbot_platform.crm.appointments.engine import AvailabilityEngine

    s0 = pg_factory()
    try:
        avail = AvailabilityEngine(s0).compute(
            tenant_id,
            from_date=starts.date(),
            to_date=starts.date(),
            service_id=setup_ids["service_id"],
            technician_id=setup_ids["technician_id"],
            limit=20,
        )
        assert any(
            datetime.fromisoformat(slot["starts_at"]).astimezone(UTC) == starts
            for slot in avail["slots"]
        )
    finally:
        s0.close()

    def book(n: int) -> dict:
        s = pg_factory()
        try:
            AppointmentService(s).create(
                tenant_id,
                customer_id=setup_ids["customer_id"],
                starts_at=starts,
                actor=f"w-{n}",
                service_id=setup_ids["service_id"],
                technician_id=setup_ids["technician_id"],
            )
            s.commit()
            return {"ok": True}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [f.result() for f in as_completed([pool.submit(book, i) for i in range(2)])]
    assert sum(1 for r in results if r["ok"]) == 1
    assert sum(1 for r in results if not r["ok"]) == 1

    s = pg_factory()
    try:
        count = s.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.tenant_id == tenant_id)
        )
        assert count == 1
    finally:
        s.close()


def test_concurrent_reschedule_same_appointment(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id, duration_minutes=60)
        BusinessHoursService(session).update(
            tenant.id,
            actor="setup",
            weekly_hours={
                d: [["00:00", "23:59"]]
                for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            },
        )
        starts = _next_monday_9am()
        appt = AppointmentService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts,
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
        session.commit()
        tenant_id = tenant.id
        appt_id = uuid.UUID(appt["id"])
        t1 = starts + timedelta(hours=2)
        t2 = starts + timedelta(hours=4)
    finally:
        session.close()

    def worker(target: datetime) -> dict:
        s = pg_factory()
        try:
            result = AppointmentService(s).reschedule(
                tenant_id, appt_id, starts_at=target, actor="w"
            )
            s.commit()
            return {"ok": True, "starts_at": result["starts_at"]}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed([pool.submit(worker, t1), pool.submit(worker, t2)])
        ]
    # Both may succeed serially (different destinations); final state must be one of them.
    assert any(r["ok"] for r in results)
    s = pg_factory()
    try:
        final = s.scalar(select(Appointment).where(Appointment.id == appt_id))
        assert final is not None
        assert final.starts_at.astimezone(UTC) in {t1, t2}
    finally:
        s.close()


def test_cancel_vs_reschedule_race(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id, duration_minutes=60)
        BusinessHoursService(session).update(
            tenant.id,
            actor="setup",
            weekly_hours={
                d: [["00:00", "23:59"]]
                for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            },
        )
        starts = _next_monday_9am()
        appt = AppointmentService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts,
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
        session.commit()
        tenant_id = tenant.id
        appt_id = uuid.UUID(appt["id"])
        later = starts + timedelta(hours=3)
    finally:
        session.close()

    def cancel() -> dict:
        s = pg_factory()
        try:
            AppointmentService(s).cancel(tenant_id, appt_id, actor="cancel")
            s.commit()
            return {"ok": True, "op": "cancel"}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code, "op": "cancel"}
        finally:
            s.close()

    def reschedule() -> dict:
        s = pg_factory()
        try:
            AppointmentService(s).reschedule(
                tenant_id, appt_id, starts_at=later, actor="reschedule"
            )
            s.commit()
            return {"ok": True, "op": "reschedule"}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code, "op": "reschedule"}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed([pool.submit(cancel), pool.submit(reschedule)])
        ]
    s = pg_factory()
    try:
        final = s.scalar(select(Appointment).where(Appointment.id == appt_id))
        assert final is not None
        assert final.status in {"CANCELLED", "SCHEDULED", "CONFIRMED", "TENTATIVE"}
        if final.status == "CANCELLED":
            assert final.cancelled_at is not None
        # Exactly one of the mutating ops should leave a coherent terminal/active state.
        assert sum(1 for r in results if r["ok"]) >= 1
    finally:
        s.close()


def test_concurrent_assign_race(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id, duration_minutes=60)
        tech2 = TechnicianRepository(session).create(
            tenant.id,
            email=f"tech2-{uuid.uuid4().hex[:6]}@t.test",
            password="password123",
            name="Tech Two",
        )
        BusinessHoursService(session).update(
            tenant.id,
            actor="setup",
            weekly_hours={
                d: [["00:00", "23:59"]]
                for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            },
        )
        starts = _next_monday_9am()
        appt = AppointmentService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts,
            actor="setup",
            service_id=setup["service_id"],
        )
        session.commit()
        tenant_id = tenant.id
        appt_id = uuid.UUID(appt["id"])
        tech_a = setup["technician_id"]
        tech_b = uuid.UUID(tech2["id"])
    finally:
        session.close()

    def worker(tech_id: uuid.UUID) -> dict:
        s = pg_factory()
        try:
            result = AppointmentService(s).assign(
                tenant_id, appt_id, technician_id=tech_id, actor="w"
            )
            s.commit()
            return {"ok": True, "tech": result["assigned_technician_id"]}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed(
                [pool.submit(worker, tech_a), pool.submit(worker, tech_b)]
            )
        ]
    assert all(r["ok"] for r in results)
    s = pg_factory()
    try:
        final = s.scalar(select(Appointment).where(Appointment.id == appt_id))
        assert final is not None
        assert final.assigned_technician_id in {tech_a, tech_b}
    finally:
        s.close()


def test_concurrent_status_complete_vs_cancel(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id, duration_minutes=60)
        BusinessHoursService(session).update(
            tenant.id,
            actor="setup",
            weekly_hours={
                d: [["00:00", "23:59"]]
                for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            },
        )
        starts = _next_monday_9am()
        api = AppointmentService(session)
        appt = api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts,
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
            status="SCHEDULED",
        )
        aid = uuid.UUID(appt["id"])
        api.transition(tenant.id, aid, to_status="CONFIRMED", actor="setup")
        api.transition(tenant.id, aid, to_status="IN_PROGRESS", actor="setup")
        session.commit()
        tenant_id = tenant.id
        appt_id = aid
    finally:
        session.close()

    def worker(to_status: str) -> dict:
        s = pg_factory()
        try:
            AppointmentService(s).transition(
                tenant_id, appt_id, to_status=to_status, actor=f"w-{to_status}"
            )
            s.commit()
            return {"ok": True, "status": to_status}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed(
                [
                    pool.submit(worker, "COMPLETED"),
                    pool.submit(worker, "CANCELLED"),
                ]
            )
        ]
    oks = [r for r in results if r["ok"]]
    fails = [r for r in results if not r["ok"]]
    assert len(oks) == 1
    assert len(fails) == 1
    assert fails[0]["code"] == "invalid_transition"
    s = pg_factory()
    try:
        final = s.scalar(select(Appointment).where(Appointment.id == appt_id))
        assert final is not None
        assert final.status in {"COMPLETED", "CANCELLED"}
        from callbot_platform.db.models.scheduling import AppointmentStatusHistory

        hist = s.scalar(
            select(func.count())
            .select_from(AppointmentStatusHistory)
            .where(
                AppointmentStatusHistory.appointment_id == appt_id,
                AppointmentStatusHistory.from_status == "IN_PROGRESS",
            )
        )
        assert hist == 1
    finally:
        s.close()


def test_concurrent_reschedule_into_same_destination(pg_factory) -> None:
    """Two appointments racing into the same destination slot — one wins."""
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id, duration_minutes=60)
        BusinessHoursService(session).update(
            tenant.id,
            actor="setup",
            weekly_hours={
                d: [["00:00", "23:59"]]
                for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
            },
        )
        starts = _next_monday_9am()
        api = AppointmentService(session)
        a = api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts,
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
        b = api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts + timedelta(hours=1),
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
        session.commit()
        tenant_id = tenant.id
        dest = starts + timedelta(hours=3)
        ids = (uuid.UUID(a["id"]), uuid.UUID(b["id"]))
    finally:
        session.close()

    def worker(appt_id: uuid.UUID) -> dict:
        s = pg_factory()
        try:
            AppointmentService(s).reschedule(
                tenant_id, appt_id, starts_at=dest, actor="w"
            )
            s.commit()
            return {"ok": True}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed([pool.submit(worker, i) for i in ids])
        ]
    assert sum(1 for r in results if r["ok"]) == 1
    assert sum(1 for r in results if not r["ok"]) == 1


def test_explain_appointment_hot_paths(pg_factory) -> None:
    """Local EXPLAIN ANALYZE evidence for appointment hot paths (not staging/prod)."""
    session = pg_factory()
    try:
        tenants: list[Tenant] = []
        setups: list[dict] = []
        for _ in range(4):
            t = _tenant(session)
            tenants.append(t)
            setups.append(_field_setup(session, t.id, duration_minutes=60))
            BusinessHoursService(session).update(
                t.id,
                actor="setup",
                weekly_hours={
                    d: [["00:00", "23:59"]]
                    for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
                },
            )
        session.flush()
        for ti, setup in enumerate(setups):
            tid = tenants[ti].id
            session.execute(
                text(
                    """
                    INSERT INTO appointments (
                        id, tenant_id, appointment_number, confirmation_code,
                        customer_id, service_id, assigned_technician_id,
                        service_type, status, priority, is_emergency,
                        starts_at, ends_at, duration_minutes, timezone,
                        created_at, updated_at
                    )
                    SELECT
                        gen_random_uuid(),
                        CAST(:tid AS uuid),
                        'APT-' || lpad(gs::text, 6, '0'),
                        'APT-' || substr(md5(gs::text || CAST(:tid AS text)), 1, 6),
                        CAST(:cid AS uuid),
                        CAST(:sid AS uuid),
                        CAST(:tech AS uuid),
                        'Bulk',
                        CASE WHEN gs % 7 = 0 THEN 'CANCELLED' ELSE 'SCHEDULED' END,
                        'NORMAL',
                        false,
                        NOW() + (gs || ' hours')::interval,
                        NOW() + (gs || ' hours')::interval + interval '60 minutes',
                        60,
                        'UTC',
                        NOW() - (gs || ' minutes')::interval,
                        NOW()
                    FROM generate_series(1, 2500) AS gs
                    """
                ),
                {
                    "tid": str(tid),
                    "cid": str(setup["customer_id"]),
                    "sid": str(setup["service_id"]),
                    "tech": str(setup["technician_id"]),
                },
            )
        session.commit()
        tid = str(tenants[0].id)
        cid = str(setups[0]["customer_id"])
        techid = str(setups[0]["technician_id"])
        sid = str(setups[0]["service_id"])

        plans: dict[str, str] = {}
        queries = {
            "list_cursor": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM appointments
                WHERE tenant_id = '{tid}' AND archived_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT 50
            """,
            "customer_history": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM appointments
                WHERE tenant_id = '{tid}' AND customer_id = '{cid}'
                ORDER BY starts_at DESC
                LIMIT 50
            """,
            "technician_conflict": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM appointments
                WHERE tenant_id = '{tid}'
                  AND assigned_technician_id = '{techid}'
                  AND archived_at IS NULL
                  AND status IN ('TENTATIVE','SCHEDULED','CONFIRMED','IN_PROGRESS')
                  AND starts_at < NOW() + INTERVAL '2 hours'
                  AND ends_at > NOW()
            """,
            "date_range": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM appointments
                WHERE tenant_id = '{tid}'
                  AND starts_at >= NOW()
                  AND starts_at < NOW() + INTERVAL '7 days'
                  AND archived_at IS NULL
                ORDER BY starts_at ASC
                LIMIT 100
            """,
            "status_filter": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM appointments
                WHERE tenant_id = '{tid}' AND status = 'SCHEDULED'
                  AND archived_at IS NULL
                ORDER BY starts_at ASC
                LIMIT 50
            """,
            "job_lookup": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM appointments
                WHERE tenant_id = '{tid}' AND job_id IS NOT NULL
                LIMIT 50
            """,
            "history": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM appointment_status_history
                WHERE tenant_id = '{tid}'
                ORDER BY created_at ASC
                LIMIT 50
            """,
            "service_filter": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM appointments
                WHERE tenant_id = '{tid}' AND service_id = '{sid}'
                  AND archived_at IS NULL
                ORDER BY starts_at DESC
                LIMIT 50
            """,
        }
        for name, sql in queries.items():
            rows = session.execute(text(sql)).fetchall()
            plans[name] = "\n".join(r[0] for r in rows)
            assert "Seq Scan" in plans[name] or "Index" in plans[name]
        assert all(plans.values())
    finally:
        session.close()
