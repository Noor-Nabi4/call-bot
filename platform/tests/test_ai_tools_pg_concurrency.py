"""PostgreSQL concurrency / isolation tests for Phase 14 AI tools.

Skip when Postgres is unavailable — SQLite cannot prove advisory locks,
exclusion constraints, or unique phone races under real isolation.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.ai_tools import AIToolExecutor
from callbot_platform.crm.appointments.hours import BusinessHoursService
from callbot_platform.crm.appointments.service import AppointmentService
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.inventory import InventoryService
from callbot_platform.crm.orders import OrderService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Base, Call, CustomerPhone, Tenant
from callbot_platform.db.models.inventory import InventoryBalance
from callbot_platform.db.models.jobs import Job
from callbot_platform.db.models.orders import Order
from callbot_platform.db.models.scheduling import Appointment, NotificationOutbox
from callbot_platform.jobs.repos import TechnicianRepository
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

HMAC = "test-metadata-hmac-secret-ai-tools-pg"

PG_URL = os.environ.get(
    "AI_TOOLS_PG_TEST_URL",
    os.environ.get(
        "APPOINTMENTS_PG_TEST_URL",
        os.environ.get(
            "ORDERS_PG_TEST_URL",
            os.environ.get(
                "INVENTORY_PG_TEST_URL",
                "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
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
    reason="PostgreSQL not available for AI tools concurrency tests",
)


@pytest.fixture()
def pg_factory():
    engine = create_engine(PG_URL, future=True, pool_size=12, max_overflow=8)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
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


def _executor(session: Session) -> AIToolExecutor:
    return AIToolExecutor(session, hmac_secret=HMAC)


def _tenant(session: Session, *, name: str = "AI Tools PG") -> Tenant:
    row = Tenant(name=name, slug=f"ai-pg-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    ensure_system_roles_for_tenant(session, row.id)
    return row


def _call(session: Session, tenant_id: uuid.UUID, *, phone: str) -> Call:
    row = Call(
        tenant_id=tenant_id,
        room_name=f"room-{uuid.uuid4().hex[:8]}",
        caller_number=phone,
        status="active",
    )
    session.add(row)
    session.flush()
    return row


def _next_monday_9am() -> datetime:
    now = datetime.now(UTC)
    days_ahead = (7 - now.weekday()) % 7 or 7
    day = (now + timedelta(days=days_ahead)).date()
    return datetime(day.year, day.month, day.day, 9, 0, tzinfo=UTC)


def _open_hours(session: Session, tenant_id: uuid.UUID) -> None:
    BusinessHoursService(session).update(
        tenant_id,
        actor="setup",
        weekly_hours={
            d: [["00:00", "23:59"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
    )


def _mutate(
    session: Session,
    tool: str,
    *,
    tenant_id: uuid.UUID,
    args: dict,
    call_id: uuid.UUID | None = None,
    customer_id: uuid.UUID | None = None,
    operation_id: uuid.UUID | None = None,
) -> dict:
    ex = _executor(session)
    op = operation_id or uuid.uuid4()
    prep = ex.execute(
        tool,
        tenant_id=tenant_id,
        call_id=call_id,
        args=args,
        confirmed=False,
        operation_id=op,
        customer_id=customer_id,
    )
    if (
        not prep.get("ok")
        and (prep.get("error") or {}).get("code") != "confirmation_required"
    ):
        return prep
    token = prep.get("confirmationToken")
    return ex.execute(
        tool,
        tenant_id=tenant_id,
        call_id=call_id,
        args=args,
        confirmed=True,
        confirmation_token=token,
        operation_id=op,
        customer_id=customer_id,
    )


def _field_setup(session: Session, tenant_id: uuid.UUID) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Buyer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="setup",
    )
    service = ServicesPricebookService(session).create_service(
        tenant_id, name="Repair", actor="setup", duration_minutes=60
    )
    tech = TechnicianRepository(session).create(
        tenant_id,
        email=f"tech-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Field Tech",
    )
    _open_hours(session, tenant_id)
    return {
        "customer_id": uuid.UUID(customer["id"]),
        "service_id": uuid.UUID(service["id"]),
        "technician_id": uuid.UUID(tech["id"]),
    }


def _commerce(session: Session, tenant_id: uuid.UUID, *, qty: int = 50) -> dict:
    catalog = ProductCatalogService(session)
    prod = catalog.create(
        tenant_id,
        name="Widget",
        sku=f"W-{uuid.uuid4().hex[:6]}",
        price="10",
        actor="setup",
    )
    variant = catalog.variants.create(
        tenant_id,
        uuid.UUID(prod["id"]),
        sku=f"W-{uuid.uuid4().hex[:6]}-A",
        actor="setup",
    )
    inv = InventoryService(session)
    loc = inv.locations.create(
        tenant_id,
        name="Main",
        code=f"M-{uuid.uuid4().hex[:4]}",
        actor="setup",
        is_default=True,
    )
    item = inv.items.ensure_for_variant(
        tenant_id, uuid.UUID(variant["id"]), actor="setup"
    )
    inv.mutations.purchase(
        tenant_id,
        item.id,
        location_id=uuid.UUID(loc["id"]),
        quantity=qty,
        actor="setup",
    )
    customer = CustomerService(session).create(
        tenant_id,
        name="Buyer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="setup",
    )
    return {
        "product_id": uuid.UUID(prod["id"]),
        "variant_id": uuid.UUID(variant["id"]),
        "location_id": uuid.UUID(loc["id"]),
        "item_id": item.id,
        "customer_id": uuid.UUID(customer["id"]),
    }


def test_customer_creation_race_same_phone(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        session.commit()
        tenant_id = tenant.id
    finally:
        session.close()

    phone = f"+1555{uuid.uuid4().int % 10_000_000:07d}"

    def worker(n: int) -> dict:
        s = pg_factory()
        try:
            result = _mutate(
                s,
                "create_customer",
                tenant_id=tenant_id,
                args={"firstName": f"Caller{n}", "phone": phone},
                operation_id=uuid.uuid4(),
            )
            s.commit()
            return result
        except Exception as exc:
            s.rollback()
            return {
                "ok": False,
                "error": {"code": "exception", "message": type(exc).__name__},
            }
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = list(pool.map(worker, range(6)))

    oks = [r for r in results if r.get("ok")]
    assert len(oks) == 6
    created = [r for r in oks if r["data"].get("created") is True]
    reused = [r for r in oks if r["data"].get("created") is False]
    assert len(created) == 1
    assert len(reused) == 5
    winner_id = created[0]["data"]["customer"]["id"]
    assert all(r["data"]["customer"]["id"] == winner_id for r in oks)

    s = pg_factory()
    try:
        count = s.scalar(
            select(func.count())
            .select_from(CustomerPhone)
            .where(
                CustomerPhone.tenant_id == tenant_id,
                CustomerPhone.e164 == phone,
            )
        )
        assert count == 1
    finally:
        s.close()


def test_duplicate_booking_race_different_operation_ids(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
        starts = _next_monday_9am()
        ends = starts + timedelta(hours=1)
    finally:
        session.close()

    args_base = {
        "customerId": str(setup_ids["customer_id"]),
        "serviceId": str(setup_ids["service_id"]),
        "technicianId": str(setup_ids["technician_id"]),
        "startsAt": starts.isoformat(),
        "endsAt": ends.isoformat(),
        "timezone": "UTC",
        "description": "Voice booking race",
    }

    def worker(n: int) -> dict:
        s = pg_factory()
        try:
            result = _mutate(
                s,
                "create_booking",
                tenant_id=tenant_id,
                args=args_base,
                operation_id=uuid.uuid4(),
            )
            s.commit()
            return result
        except Exception as exc:
            s.rollback()
            return {
                "ok": False,
                "error": {"code": "exception", "detail": type(exc).__name__},
            }
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = [
            f.result() for f in as_completed([pool.submit(worker, n) for n in range(4)])
        ]

    oks = [
        r
        for r in results
        if r.get("ok") and r.get("data", {}).get("booking") == "CREATED"
    ]
    conflicts = [
        r
        for r in results
        if (
            not r.get("ok") and (r.get("error") or {}).get("code") == "booking_conflict"
        )
        or (r.get("ok") and r.get("data", {}).get("booking") == "CONFLICT")
    ]
    assert len(oks) == 1, results
    assert len(conflicts) >= 1

    s = pg_factory()
    try:
        jobs = s.scalar(
            select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id)
        )
        appts = s.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(Appointment.tenant_id == tenant_id)
        )
        assert jobs == 1
        assert appts == 1
    finally:
        s.close()


def test_same_operation_booking_race(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
        starts = _next_monday_9am()
        ends = starts + timedelta(hours=1)
        op = uuid.uuid4()
    finally:
        session.close()

    args = {
        "customerId": str(setup_ids["customer_id"]),
        "serviceId": str(setup_ids["service_id"]),
        "technicianId": str(setup_ids["technician_id"]),
        "startsAt": starts.isoformat(),
        "endsAt": ends.isoformat(),
        "timezone": "UTC",
        "description": "Same op booking",
    }

    def worker(_: int) -> dict:
        s = pg_factory()
        try:
            result = _mutate(
                s,
                "create_booking",
                tenant_id=tenant_id,
                args=args,
                operation_id=op,
            )
            s.commit()
            return result
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(worker, range(4)))

    assert all(r.get("ok") for r in results), results
    booking_ids = {r["data"]["appointment"]["id"] for r in results}
    job_ids = {r["data"]["job"]["id"] for r in results}
    assert len(booking_ids) == 1
    assert len(job_ids) == 1

    s = pg_factory()
    try:
        assert (
            s.scalar(
                select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id)
            )
            == 1
        )
        assert (
            s.scalar(
                select(func.count())
                .select_from(Appointment)
                .where(Appointment.tenant_id == tenant_id)
            )
            == 1
        )
    finally:
        s.close()


def test_idempotency_payload_conflict_matrix(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id)
        commerce = _commerce(session, tenant.id, qty=20)
        starts = _next_monday_9am()
        appt_reschedule = AppointmentService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts + timedelta(days=1),
            ends_at=starts + timedelta(days=1, hours=1),
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
        appt_cancel = AppointmentService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts + timedelta(days=6),
            ends_at=starts + timedelta(days=6, hours=1),
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
        session.commit()
        tenant_id = tenant.id
        customer_id = setup["customer_id"]
        service_id = setup["service_id"]
        tech_id = setup["technician_id"]
        appt_reschedule_id = uuid.UUID(appt_reschedule["id"])
        appt_cancel_id = uuid.UUID(appt_cancel["id"])
        variant_id = commerce["variant_id"]
        commerce_customer = commerce["customer_id"]
    finally:
        session.close()

    cases: list[tuple[str, dict, dict]] = [
        (
            "create_customer",
            {"firstName": "A", "phone": f"+1555{uuid.uuid4().int % 10_000_000:07d}"},
            {"firstName": "B", "phone": f"+1555{uuid.uuid4().int % 10_000_000:07d}"},
        ),
        (
            "update_customer",
            {
                "customerId": str(customer_id),
                "firstName": "UpdatedA",
                "email": "a@example.com",
            },
            {
                "customerId": str(customer_id),
                "firstName": "UpdatedB",
                "email": "b@example.com",
            },
        ),
        (
            "create_booking",
            {
                "customerId": str(customer_id),
                "serviceId": str(service_id),
                "technicianId": str(tech_id),
                "startsAt": (starts + timedelta(days=2)).isoformat(),
                "endsAt": (starts + timedelta(days=2, hours=1)).isoformat(),
                "timezone": "UTC",
                "description": "payload A",
            },
            {
                "customerId": str(customer_id),
                "serviceId": str(service_id),
                "technicianId": str(tech_id),
                "startsAt": (starts + timedelta(days=3)).isoformat(),
                "endsAt": (starts + timedelta(days=3, hours=1)).isoformat(),
                "timezone": "UTC",
                "description": "payload B",
            },
        ),
        (
            "reschedule_appointment",
            {
                "appointmentId": str(appt_reschedule_id),
                "startsAt": (starts + timedelta(days=4)).isoformat(),
                "endsAt": (starts + timedelta(days=4, hours=1)).isoformat(),
                "timezone": "UTC",
            },
            {
                "appointmentId": str(appt_reschedule_id),
                "startsAt": (starts + timedelta(days=5)).isoformat(),
                "endsAt": (starts + timedelta(days=5, hours=1)).isoformat(),
                "timezone": "UTC",
            },
        ),
        (
            "cancel_appointment",
            {"appointmentId": str(appt_cancel_id), "reason": "reason-a"},
            {"appointmentId": str(appt_cancel_id), "reason": "reason-b"},
        ),
        (
            "create_order",
            {
                "customerId": str(commerce_customer),
                "items": [{"variantId": str(variant_id), "quantity": 1}],
            },
            {
                "customerId": str(commerce_customer),
                "items": [{"variantId": str(variant_id), "quantity": 2}],
            },
        ),
        (
            "send_sms",
            {
                "customerId": str(customer_id),
                "message": "Hello A",
                "purpose": "GENERAL",
            },
            {
                "customerId": str(customer_id),
                "message": "Hello B",
                "purpose": "GENERAL",
            },
        ),
    ]

    for tool, args_a, args_b in cases:
        op = uuid.uuid4()
        s = pg_factory()
        try:
            first = _mutate(s, tool, tenant_id=tenant_id, args=args_a, operation_id=op)
            assert first.get("ok") is True, (tool, first)
            s.commit()
        finally:
            s.close()

        s2 = pg_factory()
        try:
            second = _mutate(
                s2, tool, tenant_id=tenant_id, args=args_b, operation_id=op
            )
            assert second.get("ok") is False, (tool, second)
            assert second["error"]["code"] == "idempotency_conflict", (tool, second)
            s2.rollback()
        finally:
            s2.close()


def test_cross_call_idempotency_is_tenant_scoped(pg_factory) -> None:
    """Idempotency is tenant+tool+operation_id scoped — not call-scoped."""
    session = pg_factory()
    try:
        tenant = _tenant(session)
        phone = f"+1555{uuid.uuid4().int % 10_000_000:07d}"
        call_a = _call(session, tenant.id, phone=phone)
        call_b = _call(session, tenant.id, phone=phone)
        session.commit()
        tenant_id = tenant.id
        call_a_id = call_a.id
        call_b_id = call_b.id
        op = uuid.uuid4()
        args = {"firstName": "Shared", "phone": phone}
    finally:
        session.close()

    s = pg_factory()
    try:
        first = _mutate(
            s,
            "create_customer",
            tenant_id=tenant_id,
            call_id=call_a_id,
            args=args,
            operation_id=op,
        )
        assert first["ok"] is True
        s.commit()
        customer_id = first["data"]["customer"]["id"]
    finally:
        s.close()

    s2 = pg_factory()
    try:
        second = _mutate(
            s2,
            "create_customer",
            tenant_id=tenant_id,
            call_id=call_b_id,
            args=args,
            operation_id=op,
        )
        assert second["ok"] is True
        assert second.get("meta", {}).get("replay") is True
        assert second["data"]["customer"]["id"] == customer_id
        s2.commit()
    finally:
        s2.close()

    s3 = pg_factory()
    try:
        count = s3.scalar(
            select(func.count())
            .select_from(CustomerPhone)
            .where(CustomerPhone.tenant_id == tenant_id, CustomerPhone.e164 == phone)
        )
        assert count == 1
    finally:
        s3.close()


def test_cross_tenant_idempotency_isolation(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant_a = _tenant(session, name="Tenant A")
        tenant_b = _tenant(session, name="Tenant B")
        phone_a = f"+1555{uuid.uuid4().int % 10_000_000:07d}"
        phone_b = f"+1555{uuid.uuid4().int % 10_000_000:07d}"
        session.commit()
        ta, tb = tenant_a.id, tenant_b.id
        op = uuid.uuid4()
    finally:
        session.close()

    s = pg_factory()
    try:
        a = _mutate(
            s,
            "create_customer",
            tenant_id=ta,
            args={"firstName": "Alice", "phone": phone_a},
            operation_id=op,
        )
        assert a["ok"] is True
        s.commit()
        alice_id = a["data"]["customer"]["id"]
    finally:
        s.close()

    s2 = pg_factory()
    try:
        b = _mutate(
            s2,
            "create_customer",
            tenant_id=tb,
            args={"firstName": "Bob", "phone": phone_b},
            operation_id=op,
        )
        assert b["ok"] is True
        assert b.get("meta", {}).get("replay") is not True
        assert b["data"]["customer"]["id"] != alice_id
        s2.commit()
    finally:
        s2.close()


def test_booking_after_availability_race(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
        starts = _next_monday_9am()
        ends = starts + timedelta(hours=1)
    finally:
        session.close()

    s = pg_factory()
    try:
        avail = _executor(s).execute(
            "check_availability",
            tenant_id=tenant_id,
            call_id=None,
            args={
                "serviceId": str(setup_ids["service_id"]),
                "technicianId": str(setup_ids["technician_id"]),
                "preferredDate": starts.date().isoformat(),
                "limit": 5,
            },
        )
        assert avail["ok"] is True
        s.commit()
    finally:
        s.close()

    args = {
        "customerId": str(setup_ids["customer_id"]),
        "serviceId": str(setup_ids["service_id"]),
        "technicianId": str(setup_ids["technician_id"]),
        "startsAt": starts.isoformat(),
        "endsAt": ends.isoformat(),
        "timezone": "UTC",
        "description": "After availability",
    }

    def worker(n: int) -> dict:
        sess = pg_factory()
        try:
            result = _mutate(
                sess,
                "create_booking",
                tenant_id=tenant_id,
                args=args,
                operation_id=uuid.uuid4(),
            )
            sess.commit()
            return result
        finally:
            sess.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, range(2)))

    oks = [
        r
        for r in results
        if r.get("ok") and r.get("data", {}).get("booking") == "CREATED"
    ]
    conflicts = [
        r
        for r in results
        if (
            not r.get("ok") and (r.get("error") or {}).get("code") == "booking_conflict"
        )
    ]
    assert len(oks) == 1
    assert len(conflicts) == 1
    err = conflicts[0]["error"]
    assert err.get("customerSafe") is True
    assert err.get("retryable") is True


def test_reschedule_race_two_destinations(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id)
        starts = _next_monday_9am()
        appt = AppointmentService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
        session.commit()
        tenant_id = tenant.id
        appt_id = uuid.UUID(appt["id"])
        slot_x = starts + timedelta(days=1)
        slot_y = starts + timedelta(days=2)
    finally:
        session.close()

    def worker(slot: datetime) -> dict:
        s = pg_factory()
        try:
            result = _mutate(
                s,
                "reschedule_appointment",
                tenant_id=tenant_id,
                args={
                    "appointmentId": str(appt_id),
                    "startsAt": slot.isoformat(),
                    "endsAt": (slot + timedelta(hours=1)).isoformat(),
                    "timezone": "UTC",
                },
                operation_id=uuid.uuid4(),
            )
            s.commit()
            return result
        except Exception as exc:
            s.rollback()
            return {"ok": False, "error": {"code": type(exc).__name__}}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(worker, [slot_x, slot_y]))

    oks = [r for r in results if r.get("ok")]
    assert len(oks) >= 1
    s = pg_factory()
    try:
        row = s.get(Appointment, appt_id)
        assert row is not None
        assert row.archived_at is None
        final_start = row.starts_at
        assert final_start in {slot_x, slot_y}
        count = s.scalar(
            select(func.count())
            .select_from(Appointment)
            .where(
                Appointment.tenant_id == tenant_id,
                Appointment.id == appt_id,
            )
        )
        assert count == 1
    finally:
        s.close()


def test_reschedule_vs_conflicting_book(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id)
        starts = _next_monday_9am()
        appt = AppointmentService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
        appt_id = uuid.UUID(appt["id"])
        target = starts + timedelta(days=1)
    finally:
        session.close()

    def reschedule() -> dict:
        s = pg_factory()
        try:
            result = _mutate(
                s,
                "reschedule_appointment",
                tenant_id=tenant_id,
                args={
                    "appointmentId": str(appt_id),
                    "startsAt": target.isoformat(),
                    "endsAt": (target + timedelta(hours=1)).isoformat(),
                    "timezone": "UTC",
                },
                operation_id=uuid.uuid4(),
            )
            s.commit()
            return {"kind": "reschedule", **result}
        finally:
            s.close()

    def book() -> dict:
        s = pg_factory()
        try:
            result = _mutate(
                s,
                "create_booking",
                tenant_id=tenant_id,
                args={
                    "customerId": str(setup_ids["customer_id"]),
                    "serviceId": str(setup_ids["service_id"]),
                    "technicianId": str(setup_ids["technician_id"]),
                    "startsAt": target.isoformat(),
                    "endsAt": (target + timedelta(hours=1)).isoformat(),
                    "timezone": "UTC",
                    "description": "Conflict book",
                },
                operation_id=uuid.uuid4(),
            )
            s.commit()
            return {"kind": "book", **result}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed([pool.submit(reschedule), pool.submit(book)])
        ]

    successes = []
    for r in results:
        if r.get("kind") == "reschedule" and r.get("ok"):
            successes.append("reschedule")
        if (
            r.get("kind") == "book"
            and r.get("ok")
            and r.get("data", {}).get("booking") == "CREATED"
        ):
            successes.append("book")
    assert len(successes) == 1, results

    s = pg_factory()
    try:
        active = s.scalars(
            select(Appointment).where(
                Appointment.tenant_id == tenant_id,
                Appointment.assigned_technician_id == setup_ids["technician_id"],
                Appointment.archived_at.is_(None),
                Appointment.status.in_(
                    ("TENTATIVE", "SCHEDULED", "CONFIRMED", "IN_PROGRESS")
                ),
            )
        ).all()
        # At most one active appointment occupying target window for the tech.
        overlapping = [
            a
            for a in active
            if a.starts_at < target + timedelta(hours=1) and a.ends_at > target
        ]
        assert len(overlapping) == 1
    finally:
        s.close()


def test_cancel_vs_reschedule_race(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_setup(session, tenant.id)
        starts = _next_monday_9am()
        appt = AppointmentService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            starts_at=starts,
            ends_at=starts + timedelta(hours=1),
            actor="setup",
            service_id=setup["service_id"],
            technician_id=setup["technician_id"],
        )
        session.commit()
        tenant_id = tenant.id
        appt_id = uuid.UUID(appt["id"])
        original_starts = starts
        target = starts + timedelta(days=1)
    finally:
        session.close()

    def cancel() -> dict:
        s = pg_factory()
        try:
            result = _mutate(
                s,
                "cancel_appointment",
                tenant_id=tenant_id,
                args={"appointmentId": str(appt_id), "reason": "caller cancelled"},
                operation_id=uuid.uuid4(),
            )
            s.commit()
            return {"kind": "cancel", **result}
        finally:
            s.close()

    def reschedule() -> dict:
        s = pg_factory()
        try:
            result = _mutate(
                s,
                "reschedule_appointment",
                tenant_id=tenant_id,
                args={
                    "appointmentId": str(appt_id),
                    "startsAt": target.isoformat(),
                    "endsAt": (target + timedelta(hours=1)).isoformat(),
                    "timezone": "UTC",
                },
                operation_id=uuid.uuid4(),
            )
            s.commit()
            return {"kind": "reschedule", **result}
        except Exception as exc:
            s.rollback()
            return {
                "kind": "reschedule",
                "ok": False,
                "error": {"code": type(exc).__name__},
            }
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed([pool.submit(cancel), pool.submit(reschedule)])
        ]

    oks = [r for r in results if r.get("ok")]
    assert len(oks) >= 1
    s = pg_factory()
    try:
        row = s.get(Appointment, appt_id)
        assert row is not None
        assert (
            s.scalar(
                select(func.count())
                .select_from(Appointment)
                .where(Appointment.id == appt_id)
            )
            == 1
        )
        # Authoritative final state: cancelled OR moved to target — never an invalid hybrid.
        if row.status == "CANCELLED":
            # Cancel may win first (original slot) or after a successful reschedule.
            assert row.starts_at in {original_starts, target}
        else:
            assert row.starts_at == target
            assert row.status in {
                "TENTATIVE",
                "SCHEDULED",
                "CONFIRMED",
                "IN_PROGRESS",
            }
    finally:
        s.close()


def test_order_creation_race_inventory(pg_factory) -> None:
    """AI create_order drafts freely; inventory authority is on confirm reserve.

    Concurrent confirmations against stock=5 must not oversell reservations.
    """
    session = pg_factory()
    try:
        tenant = _tenant(session)
        commerce = _commerce(session, tenant.id, qty=5)
        session.commit()
        tenant_id = tenant.id
        setup = commerce
    finally:
        session.close()

    def create_worker(n: int) -> dict:
        s = pg_factory()
        try:
            result = _mutate(
                s,
                "create_order",
                tenant_id=tenant_id,
                args={
                    "customerId": str(setup["customer_id"]),
                    "items": [{"variantId": str(setup["variant_id"]), "quantity": 1}],
                },
                operation_id=uuid.uuid4(),
            )
            s.commit()
            return result
        except Exception as exc:
            s.rollback()
            return {"ok": False, "error": {"code": type(exc).__name__}}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        created = list(pool.map(create_worker, range(8)))

    oks = [r for r in created if r.get("ok")]
    assert len(oks) == 8
    order_ids = [uuid.UUID(r["data"]["order"]["id"]) for r in oks]

    def confirm_worker(order_id: uuid.UUID) -> dict:
        s = pg_factory()
        try:
            api = OrderService(s)
            api.transition(tenant_id, order_id, to_status="PENDING", actor="race")
            api.transition(tenant_id, order_id, to_status="CONFIRMED", actor="race")
            s.commit()
            return {"ok": True, "id": str(order_id)}
        except Exception as exc:
            s.rollback()
            code = getattr(exc, "code", type(exc).__name__)
            return {"ok": False, "code": code, "id": str(order_id)}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        confirms = list(pool.map(confirm_worker, order_ids))

    confirmed = [r for r in confirms if r.get("ok")]
    failed = [r for r in confirms if not r.get("ok")]
    assert len(confirmed) == 5, (len(confirmed), confirms)
    assert len(failed) == 3

    s = pg_factory()
    try:
        bal = s.scalar(
            select(InventoryBalance).where(
                InventoryBalance.tenant_id == tenant_id,
                InventoryBalance.inventory_item_id == setup["item_id"],
                InventoryBalance.location_id == setup["location_id"],
            )
        )
        assert bal is not None
        assert bal.stock_quantity >= 0
        assert bal.reserved_quantity >= 0
        assert bal.reserved_quantity <= bal.stock_quantity
        assert bal.reserved_quantity == 5
        assert bal.stock_quantity == 5
    finally:
        s.close()


def test_inventory_race_with_ai_order_path(pg_factory) -> None:
    """Concurrent inventory mutation + AI order confirm keeps non-negative stock."""
    session = pg_factory()
    try:
        tenant = _tenant(session)
        commerce = _commerce(session, tenant.id, qty=10)
        order = OrderService(session).create(
            tenant.id,
            customer_id=commerce["customer_id"],
            actor="setup",
            items=[
                {
                    "product_id": commerce["product_id"],
                    "variant_id": commerce["variant_id"],
                    "quantity": 4,
                }
            ],
            fulfillment_location_id=commerce["location_id"],
        )
        oid = uuid.UUID(order["id"])
        OrderService(session).transition(
            tenant.id, oid, to_status="PENDING", actor="setup"
        )
        session.commit()
        tenant_id = tenant.id
        setup = commerce
        order_id = oid
    finally:
        session.close()

    def confirm() -> dict:
        s = pg_factory()
        try:
            OrderService(s).transition(
                tenant_id, order_id, to_status="CONFIRMED", actor="ai-path"
            )
            s.commit()
            return {"ok": True, "kind": "confirm"}
        except Exception as exc:
            s.rollback()
            return {
                "ok": False,
                "kind": "confirm",
                "code": getattr(exc, "code", type(exc).__name__),
            }
        finally:
            s.close()

    def adjust() -> dict:
        s = pg_factory()
        try:
            InventoryService(s).mutations.adjust(
                tenant_id,
                setup["item_id"],
                location_id=setup["location_id"],
                quantity_delta=-8,
                actor="warehouse",
                reason="cycle_count",
            )
            s.commit()
            return {"ok": True, "kind": "adjust"}
        except Exception as exc:
            s.rollback()
            return {
                "ok": False,
                "kind": "adjust",
                "code": getattr(exc, "code", type(exc).__name__),
            }
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed([pool.submit(confirm), pool.submit(adjust)])
        ]

    s = pg_factory()
    try:
        bal = s.scalar(
            select(InventoryBalance).where(
                InventoryBalance.tenant_id == tenant_id,
                InventoryBalance.inventory_item_id == setup["item_id"],
                InventoryBalance.location_id == setup["location_id"],
            )
        )
        assert bal is not None
        assert bal.stock_quantity >= 0
        assert bal.reserved_quantity >= 0
        assert bal.reserved_quantity <= bal.stock_quantity
        assert any(r.get("ok") for r in results)
    finally:
        s.close()


def test_same_operation_order_no_duplicate(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        commerce = _commerce(session, tenant.id, qty=10)
        session.commit()
        tenant_id = tenant.id
        setup = commerce
        op = uuid.uuid4()
    finally:
        session.close()

    args = {
        "customerId": str(setup["customer_id"]),
        "items": [{"variantId": str(setup["variant_id"]), "quantity": 1}],
    }

    def worker(_: int) -> dict:
        s = pg_factory()
        try:
            result = _mutate(
                s,
                "create_order",
                tenant_id=tenant_id,
                args=args,
                operation_id=op,
            )
            s.commit()
            return result
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(worker, range(4)))

    assert all(r.get("ok") for r in results), results
    order_ids = {r["data"]["order"]["id"] for r in results}
    assert len(order_ids) == 1
    s = pg_factory()
    try:
        assert (
            s.scalar(
                select(func.count())
                .select_from(Order)
                .where(Order.tenant_id == tenant_id)
            )
            == 1
        )
    finally:
        s.close()


def test_order_idor_matrix(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant_a = _tenant(session, name="A")
        tenant_b = _tenant(session, name="B")
        cust_a = CustomerService(session).create(
            tenant_a.id,
            name="CustA",
            phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
            actor="s",
        )
        cust_b = CustomerService(session).create(
            tenant_a.id,
            name="CustB",
            phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
            actor="s",
        )
        cust_c = CustomerService(session).create(
            tenant_b.id,
            name="CustC",
            phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
            actor="s",
        )
        order_a = Order(
            tenant_id=tenant_a.id,
            customer_id=uuid.UUID(cust_a["id"]),
            order_number=f"ORD-A-{uuid.uuid4().hex[:6].upper()}",
            status="DRAFT",
            currency="USD",
            subtotal="10.00",
            tax_total="0.00",
            discount_total="0.00",
            total="10.00",
            created_by="s",
            updated_by="s",
        )
        order_b = Order(
            tenant_id=tenant_a.id,
            customer_id=uuid.UUID(cust_b["id"]),
            order_number=f"ORD-B-{uuid.uuid4().hex[:6].upper()}",
            status="DRAFT",
            currency="USD",
            subtotal="20.00",
            tax_total="0.00",
            discount_total="0.00",
            total="20.00",
            created_by="s",
            updated_by="s",
        )
        order_c = Order(
            tenant_id=tenant_b.id,
            customer_id=uuid.UUID(cust_c["id"]),
            order_number=f"ORD-C-{uuid.uuid4().hex[:6].upper()}",
            status="DRAFT",
            currency="USD",
            subtotal="30.00",
            tax_total="0.00",
            discount_total="0.00",
            total="30.00",
            created_by="s",
            updated_by="s",
        )
        session.add_all([order_a, order_b, order_c])
        session.flush()
        session.commit()
        ta = tenant_a.id
        cust_a_id = uuid.UUID(cust_a["id"])
        cust_b_id = cust_b["id"]
        order_b_id = order_b.id
        order_c_id = order_c.id
        order_b_number = order_b.order_number
    finally:
        session.close()

    s = pg_factory()
    try:
        ex = _executor(s)
        for args in (
            {"orderId": str(order_b_id)},
            {"orderId": str(order_c_id)},
            {"orderNumber": order_b_number},
        ):
            denied = ex.execute(
                "get_order_status",
                tenant_id=ta,
                call_id=None,
                customer_id=cust_a_id,
                args=args,
            )
            assert denied["ok"] is False
            assert denied["error"]["code"] == "not_found"
            assert "20.00" not in str(denied)
            assert "30.00" not in str(denied)

        # Voice context is customer A; requesting customer B must not leak.
        find_other = ex.execute(
            "find_orders",
            tenant_id=ta,
            call_id=None,
            customer_id=cust_a_id,
            args={"customerId": cust_b_id},
        )
        assert find_other["ok"] is False
        assert find_other["error"]["code"] == "not_found"
    finally:
        s.close()


def test_read_timeout_returns_system_unavailable(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        session.commit()
        tenant_id = tenant.id
    finally:
        session.close()

    s = pg_factory()
    try:
        # Force a sub-second statement timeout then sleep past it.
        s.execute(text("SET LOCAL statement_timeout = 200"))
        try:
            s.execute(text("SELECT pg_sleep(1.5)"))
            timed_out = False
        except Exception:
            timed_out = True
            s.rollback()
        assert timed_out

        # Executor maps statement timeouts on handler DB errors to system_unavailable.
        from callbot_platform.ai_tools import handlers as handlers_mod

        original = handlers_mod.AIToolHandlers.handle_find_customer

        def _slow(self, ctx, args):
            self._session.execute(text("SELECT pg_sleep(3)"))
            return original(self, ctx, args)

        handlers_mod.AIToolHandlers.handle_find_customer = _slow  # type: ignore[method-assign]
        try:
            # Rebuild executor with patched handler class.
            result = AIToolExecutor(s, hmac_secret=HMAC).execute(
                "find_customer",
                tenant_id=tenant_id,
                call_id=None,
                args={"phone": "+15550001111"},
            )
        finally:
            handlers_mod.AIToolHandlers.handle_find_customer = original  # type: ignore[method-assign]

        assert result["ok"] is False
        assert result["error"]["code"] == "system_unavailable"
        assert result["error"]["retryable"] is True
        assert result["error"]["customerSafe"] is True
        s.rollback()
    finally:
        s.close()


def test_sms_idempotency_concurrent_and_conflict(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        customer = CustomerService(session).create(
            tenant.id,
            name="SMS Cust",
            phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
            actor="setup",
        )
        session.commit()
        tenant_id = tenant.id
        customer_id = customer["id"]
        op = uuid.uuid4()
        args = {
            "customerId": customer_id,
            "message": "Your appointment is confirmed.",
            "purpose": "APPOINTMENT_CONFIRMATION",
        }
    finally:
        session.close()

    def worker(_: int) -> dict:
        s = pg_factory()
        try:
            result = _mutate(
                s,
                "send_sms",
                tenant_id=tenant_id,
                args=args,
                operation_id=op,
            )
            s.commit()
            return result
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(worker, range(4)))

    assert all(r.get("ok") for r in results), results
    assert all(r["data"]["status"] == "QUEUED" for r in results)
    assert all(r["data"]["status"] != "DELIVERED" for r in results)
    ids = {r["data"]["notificationId"] for r in results}
    assert len(ids) == 1

    s = pg_factory()
    try:
        count = s.scalar(
            select(func.count())
            .select_from(NotificationOutbox)
            .where(NotificationOutbox.tenant_id == tenant_id)
        )
        assert count == 1
        conflict = _mutate(
            s,
            "send_sms",
            tenant_id=tenant_id,
            args={
                "customerId": customer_id,
                "message": "Different message",
                "purpose": "APPOINTMENT_CONFIRMATION",
            },
            operation_id=op,
        )
        assert conflict["ok"] is False
        assert conflict["error"]["code"] == "idempotency_conflict"
    finally:
        s.close()
