"""PostgreSQL concurrency tests for Phase 21 Equipment serial uniqueness.

Skip when Postgres is unavailable — SQLite cannot prove partial-unique races.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.equipment import EquipmentService
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import Base, Tenant
from callbot_platform.db.models.equipment import Equipment

PG_URL = os.environ.get(
    "EQUIPMENT_PG_TEST_URL",
    os.environ.get(
        "JOBS_PG_TEST_URL",
        os.environ.get(
            "INVENTORY_PG_TEST_URL",
            "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
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


pytestmark = pytest.mark.skipif(
    not _pg_available(PG_URL),
    reason="PostgreSQL not available for equipment concurrency tests",
)


@pytest.fixture()
def pg_factory():
    engine = create_engine(PG_URL, future=True, pool_size=10, max_overflow=5)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def _tenant(session: Session, *, name: str = "Equip PG") -> Tenant:
    row = Tenant(name=name, slug=f"eq-pg-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _customer(session: Session, tenant_id: uuid.UUID) -> uuid.UUID:
    row = CustomerService(session).create(
        tenant_id,
        name="Owner",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="setup",
    )
    return uuid.UUID(row["id"])


def test_partial_unique_index_exists(pg_factory) -> None:
    session = pg_factory()
    try:
        rows = session.execute(
            text(
                """
                SELECT indexname, indexdef
                FROM pg_indexes
                WHERE tablename = 'equipment'
                  AND indexname = 'uq_equipment_tenant_serial_norm'
                """
            )
        ).all()
        assert len(rows) == 1
        assert "serial_number_normalized" in rows[0][1]
        assert "WHERE" in rows[0][1].upper()
    finally:
        session.close()


def test_concurrent_duplicate_serial_same_tenant(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        customer_id = _customer(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
        serial = f"SN-{uuid.uuid4().hex[:10].upper()}"
    finally:
        session.close()

    def worker(n: int) -> str:
        s = pg_factory()
        try:
            EquipmentService(s).create(
                tenant_id,
                customer_id=customer_id,
                manufacturer="Carrier",
                model=f"M-{n}",
                actor=f"w-{n}",
                serial_number=serial,
            )
            s.commit()
            return "ok"
        except CrmError as exc:
            s.rollback()
            return exc.code
        except Exception as exc:
            s.rollback()
            return f"error:{type(exc).__name__}"
        finally:
            s.close()

    outcomes: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futures = [pool.submit(worker, i) for i in range(8)]
        for fut in as_completed(futures):
            outcomes.append(fut.result())

    assert outcomes.count("ok") == 1, outcomes
    assert all(o in {"ok", "serial_conflict"} for o in outcomes), outcomes

    verify = pg_factory()
    try:
        count = verify.scalar(
            select(func.count())
            .select_from(Equipment)
            .where(
                Equipment.tenant_id == tenant_id,
                Equipment.serial_number_normalized == serial.upper(),
            )
        )
        assert int(count or 0) == 1
    finally:
        verify.close()


def test_same_serial_different_tenants_allowed(pg_factory) -> None:
    session = pg_factory()
    try:
        t_a = _tenant(session, name="A")
        t_b = _tenant(session, name="B")
        c_a = _customer(session, t_a.id)
        c_b = _customer(session, t_b.id)
        session.commit()
        serial = f"SHARED-{uuid.uuid4().hex[:8].upper()}"
        id_a = t_a.id
        id_b = t_b.id
    finally:
        session.close()

    def create_for(tenant_id: uuid.UUID, customer_id: uuid.UUID) -> str:
        s = pg_factory()
        try:
            EquipmentService(s).create(
                tenant_id,
                customer_id=customer_id,
                manufacturer="Trane",
                model="X1",
                actor="t",
                serial_number=serial,
            )
            s.commit()
            return "ok"
        except Exception as exc:
            s.rollback()
            return f"fail:{exc}"
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        fa = pool.submit(create_for, id_a, c_a)
        fb = pool.submit(create_for, id_b, c_b)
        ra, rb = fa.result(), fb.result()

    assert ra == "ok", ra
    assert rb == "ok", rb

    verify = pg_factory()
    try:
        count = verify.scalar(
            select(func.count())
            .select_from(Equipment)
            .where(Equipment.serial_number_normalized == serial.upper())
        )
        assert int(count or 0) == 2
    finally:
        verify.close()
