"""PostgreSQL parallel concurrency tests for inventory mutations.

Requires a dedicated Postgres URL (default: call_bot_inventory_test).

Skip when Postgres is unavailable — SQLite cannot prove FOR UPDATE contention.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.inventory import InventoryService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import Base, Tenant
from callbot_platform.db.models.inventory import InventoryBalance, InventoryTransaction

PG_URL = os.environ.get(
    "INVENTORY_PG_TEST_URL",
    "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
)


def _pg_available(url: str) -> bool:
    try:
        engine = create_engine(url, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    not _pg_available(PG_URL),
    reason="PostgreSQL test database unavailable",
)


@pytest.fixture()
def pg_factory():
    engine = create_engine(PG_URL, future=True, pool_size=10, max_overflow=5)
    # Avoid metadata.drop_all: circular FK on tenants/agent_profiles has no name.
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


def _seed_balance(
    factory: sessionmaker[Session],
    *,
    stock: int,
    reserved: int = 0,
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    session = factory()
    try:
        tenant = Tenant(name="PG Conc", slug=f"pg-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        catalog = ProductCatalogService(session)
        prod = catalog.create(
            tenant.id, name="Part", sku=f"P-{uuid.uuid4().hex[:6]}", price="1", actor="t"
        )
        variant = catalog.variants.create(
            tenant.id,
            uuid.UUID(prod["id"]),
            sku=f"P-{uuid.uuid4().hex[:6]}-A",
            actor="t",
        )
        inv = InventoryService(session)
        loc = inv.locations.create(
            tenant.id, name="Main", code="MAIN", actor="t", is_default=True
        )
        item = inv.items.ensure_for_variant(
            tenant.id, uuid.UUID(variant["id"]), actor="t"
        )
        loc_id = uuid.UUID(loc["id"])
        if stock > 0:
            inv.mutations.purchase(
                tenant.id,
                item.id,
                location_id=loc_id,
                quantity=stock,
                actor="seed",
            )
        if reserved > 0:
            inv.mutations.reserve(
                tenant.id,
                item.id,
                location_id=loc_id,
                quantity=reserved,
                actor="seed",
            )
        session.commit()
        return tenant.id, item.id, loc_id
    finally:
        session.close()


def _assert_invariants(session: Session, tenant_id: uuid.UUID, item_id: uuid.UUID) -> None:
    bal = session.scalar(
        select(InventoryBalance).where(
            InventoryBalance.tenant_id == tenant_id,
            InventoryBalance.inventory_item_id == item_id,
        )
    )
    assert bal is not None
    assert bal.stock_quantity >= 0
    assert bal.reserved_quantity >= 0
    assert bal.reserved_quantity <= bal.stock_quantity
    avail = bal.stock_quantity - bal.reserved_quantity
    assert avail >= 0
    # Ledger last stock_after matches balance for latest stock-affecting txn.
    last = session.scalar(
        select(InventoryTransaction)
        .where(
            InventoryTransaction.tenant_id == tenant_id,
            InventoryTransaction.inventory_item_id == item_id,
        )
        .order_by(InventoryTransaction.created_at.desc())
    )
    assert last is not None
    assert last.stock_after == bal.stock_quantity
    assert last.reserved_after == bal.reserved_quantity


def _run_concurrent(
    factory: sessionmaker[Session],
    tenant_id: uuid.UUID,
    item_id: uuid.UUID,
    loc_id: uuid.UUID,
    ops: list[tuple[str, int]],
) -> list[str]:
    def _one(op: str, qty: int, key: str) -> str:
        db = factory()
        try:
            svc = InventoryService(db)
            kwargs = {
                "location_id": loc_id,
                "quantity": qty,
                "actor": key,
                "idempotency_key": key,
            }
            if op == "sale":
                svc.mutations.sale(tenant_id, item_id, **kwargs)
            elif op == "reserve":
                svc.mutations.reserve(tenant_id, item_id, **kwargs)
            elif op == "release":
                svc.mutations.release(tenant_id, item_id, **kwargs)
            else:
                raise AssertionError(op)
            db.commit()
            return "ok"
        except CrmError as exc:
            db.rollback()
            return exc.code
        except Exception as exc:
            db.rollback()
            return f"error:{type(exc).__name__}"
        finally:
            db.close()

    results: list[str] = []
    with ThreadPoolExecutor(max_workers=len(ops)) as pool:
        futures = [
            pool.submit(_one, op, qty, f"{op}-{i}-{uuid.uuid4().hex[:6]}")
            for i, (op, qty) in enumerate(ops)
        ]
        for fut in as_completed(futures):
            results.append(fut.result())
    return results


def test_pg_concurrent_sales(pg_factory: sessionmaker[Session]) -> None:
    tenant_id, item_id, loc_id = _seed_balance(pg_factory, stock=10)
    results = _run_concurrent(
        pg_factory, tenant_id, item_id, loc_id, [("sale", 7), ("sale", 7)]
    )
    assert results.count("ok") == 1
    assert "insufficient_stock" in results
    session = pg_factory()
    try:
        bal = session.scalar(
            select(InventoryBalance).where(
                InventoryBalance.inventory_item_id == item_id
            )
        )
        assert bal is not None
        assert bal.stock_quantity == 3
        assert bal.reserved_quantity == 0
        _assert_invariants(session, tenant_id, item_id)
    finally:
        session.close()


def test_pg_concurrent_reservations(pg_factory: sessionmaker[Session]) -> None:
    tenant_id, item_id, loc_id = _seed_balance(pg_factory, stock=10)
    results = _run_concurrent(
        pg_factory,
        tenant_id,
        item_id,
        loc_id,
        [("reserve", 7), ("reserve", 7)],
    )
    assert results.count("ok") == 1
    assert "insufficient_available" in results
    session = pg_factory()
    try:
        bal = session.scalar(
            select(InventoryBalance).where(
                InventoryBalance.inventory_item_id == item_id
            )
        )
        assert bal is not None
        assert bal.stock_quantity == 10
        assert bal.reserved_quantity == 7
        _assert_invariants(session, tenant_id, item_id)
    finally:
        session.close()


def test_pg_concurrent_sale_and_reservation(pg_factory: sessionmaker[Session]) -> None:
    tenant_id, item_id, loc_id = _seed_balance(pg_factory, stock=10)
    results = _run_concurrent(
        pg_factory,
        tenant_id,
        item_id,
        loc_id,
        [("sale", 6), ("reserve", 6)],
    )
    assert results.count("ok") == 1
    assert any(
        c in results for c in ("insufficient_stock", "insufficient_available")
    )
    session = pg_factory()
    try:
        bal = session.scalar(
            select(InventoryBalance).where(
                InventoryBalance.inventory_item_id == item_id
            )
        )
        assert bal is not None
        # Valid serialized outcomes: sale-first (stock=4, reserved=0)
        # or reserve-first (stock=10, reserved=6). Never stock=4 reserved=6.
        assert (bal.stock_quantity, bal.reserved_quantity) in {(4, 0), (10, 6)}
        _assert_invariants(session, tenant_id, item_id)
    finally:
        session.close()


def test_pg_concurrent_releases(pg_factory: sessionmaker[Session]) -> None:
    tenant_id, item_id, loc_id = _seed_balance(pg_factory, stock=10, reserved=8)
    results = _run_concurrent(
        pg_factory,
        tenant_id,
        item_id,
        loc_id,
        [("release", 6), ("release", 6)],
    )
    assert results.count("ok") == 1
    assert "insufficient_reserved" in results
    session = pg_factory()
    try:
        bal = session.scalar(
            select(InventoryBalance).where(
                InventoryBalance.inventory_item_id == item_id
            )
        )
        assert bal is not None
        assert bal.stock_quantity == 10
        assert bal.reserved_quantity == 2
        _assert_invariants(session, tenant_id, item_id)
    finally:
        session.close()
