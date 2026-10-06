"""PostgreSQL concurrency tests for Phase 13 Estimates."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.estimates import EstimateService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import Base, Tenant
from callbot_platform.db.models.estimates import Estimate, EstimateConversion

PG_URL = os.environ.get(
    "ESTIMATES_PG_TEST_URL",
    os.environ.get(
        "ORDERS_PG_TEST_URL",
        os.environ.get(
            "JOBS_PG_TEST_URL",
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


_PG_UP = _pg_available(PG_URL)

pytestmark = pytest.mark.skipif(
    not _PG_UP, reason="PostgreSQL not available for estimate concurrency tests"
)


@pytest.fixture()
def pg_factory():
    engine = create_engine(PG_URL, future=True, pool_size=10, max_overflow=5)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def _tenant(session: Session) -> Tenant:
    row = Tenant(name="Est PG", slug=f"est-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _setup(session: Session, tenant_id: uuid.UUID) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Buyer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="setup",
    )
    prod = ProductCatalogService(session).create(
        tenant_id,
        name="Widget",
        sku=f"W-{uuid.uuid4().hex[:6]}",
        price="10.00",
        actor="setup",
    )
    return {
        "customer_id": uuid.UUID(customer["id"]),
        "product_id": uuid.UUID(prod["id"]),
    }


def test_concurrent_estimate_numbering(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _setup(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
        customer_id = setup["customer_id"]
        product_id = setup["product_id"]
    finally:
        session.close()

    def worker(n: int) -> str:
        s = pg_factory()
        try:
            est = EstimateService(s).create(
                tenant_id,
                customer_id=customer_id,
                actor=f"w-{n}",
                items=[
                    {
                        "item_type": "PRODUCT",
                        "product_id": product_id,
                        "quantity": 1,
                    }
                ],
            )
            s.commit()
            return est["estimate_number"]
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        numbers = [
            f.result() for f in as_completed([pool.submit(worker, i) for i in range(8)])
        ]
    assert len(numbers) == len(set(numbers))


def test_concurrent_approval_and_conversion(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _setup(session, tenant.id)
        api = EstimateService(session)
        est = api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            items=[
                {
                    "item_type": "PRODUCT",
                    "product_id": setup["product_id"],
                    "quantity": 1,
                }
            ],
            valid_until=datetime.now(UTC) + timedelta(days=3),
        )
        api.send(tenant.id, uuid.UUID(est["id"]), actor="setup")
        session.commit()
        tenant_id = tenant.id
        estimate_id = uuid.UUID(est["id"])
    finally:
        session.close()

    def approve() -> dict:
        s = pg_factory()
        try:
            EstimateService(s).approve(tenant_id, estimate_id, actor="a")
            s.commit()
            return {"ok": True, "op": "approve"}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code, "op": "approve"}
        finally:
            s.close()

    def reject() -> dict:
        s = pg_factory()
        try:
            EstimateService(s).reject(tenant_id, estimate_id, actor="r")
            s.commit()
            return {"ok": True, "op": "reject"}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code, "op": "reject"}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed([pool.submit(approve), pool.submit(reject)])
        ]
    assert sum(1 for r in results if r["ok"]) == 1
    s = pg_factory()
    try:
        final = s.scalar(select(Estimate).where(Estimate.id == estimate_id))
        assert final is not None
        assert final.status in {"APPROVED", "REJECTED"}
    finally:
        s.close()

    # Prepare approved estimate for conversion race.
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _setup(session, tenant.id)
        api = EstimateService(session)
        est = api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            items=[
                {
                    "item_type": "PRODUCT",
                    "product_id": setup["product_id"],
                    "quantity": 1,
                }
            ],
        )
        eid = uuid.UUID(est["id"])
        api.send(tenant.id, eid, actor="setup")
        api.approve(tenant.id, eid, actor="setup")
        session.commit()
        tenant_id = tenant.id
        estimate_id = eid
    finally:
        session.close()

    def convert_worker(n: int) -> dict:
        s = pg_factory()
        try:
            res = EstimateService(s).convert(
                tenant_id,
                estimate_id,
                actor=f"c-{n}",
                target_type="ORDER",
                idempotency_key="same-convert",
            )
            s.commit()
            return {"ok": True, "target": res["conversion"]["target_id"]}
        except CrmError as e:
            s.rollback()
            return {"ok": False, "code": e.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        results = [
            f.result()
            for f in as_completed([pool.submit(convert_worker, i) for i in range(6)])
        ]
    oks = [r for r in results if r.get("ok")]
    assert len(oks) >= 1
    targets = {r["target"] for r in oks}
    assert len(targets) == 1
    s = pg_factory()
    try:
        convs = list(
            s.scalars(
                select(EstimateConversion).where(
                    EstimateConversion.estimate_id == estimate_id
                )
            ).all()
        )
        assert len(convs) == 1
        est = s.scalar(select(Estimate).where(Estimate.id == estimate_id))
        assert est is not None
        assert est.status == "CONVERTED"
    finally:
        s.close()


def test_explain_estimate_hot_paths(pg_factory) -> None:
    """Local synthetic-scale EXPLAIN for estimate list/detail/events."""
    session = pg_factory()
    try:
        tenants: list[Tenant] = []
        setups: list[dict] = []
        for _ in range(4):
            t = _tenant(session)
            tenants.append(t)
            setups.append(_setup(session, t.id))
        session.flush()
        for ti, setup in enumerate(setups):
            tid = tenants[ti].id
            session.execute(
                text(
                    """
                    INSERT INTO estimates (
                        id, tenant_id, estimate_number, customer_id, title,
                        status, currency, subtotal, discount_total, tax_total,
                        total, estimate_discount, created_at, updated_at
                    )
                    SELECT
                        gen_random_uuid(),
                        CAST(:tid AS uuid),
                        'EST-' || lpad(gs::text, 6, '0'),
                        CAST(:cid AS uuid),
                        'Bench',
                        CASE WHEN gs % 5 = 0 THEN 'APPROVED' ELSE 'DRAFT' END,
                        'USD',
                        100, 0, 0, 100, 0,
                        NOW() - (gs || ' minutes')::interval,
                        NOW()
                    FROM generate_series(1, 2500) AS gs
                    """
                ),
                {"tid": str(tid), "cid": str(setup["customer_id"])},
            )
            session.execute(
                text(
                    """
                    INSERT INTO estimate_items (
                        id, tenant_id, estimate_id, item_type, name_snapshot,
                        quantity, unit_price, discount_total, tax_total,
                        line_subtotal, line_total, sort_order, created_at, updated_at
                    )
                    SELECT
                        gen_random_uuid(),
                        e.tenant_id,
                        e.id,
                        'CUSTOM',
                        'Line',
                        1, 10, 0, 0, 10, 10, 0, NOW(), NOW()
                    FROM estimates e
                    WHERE e.tenant_id = CAST(:tid AS uuid)
                    LIMIT 7500
                    """
                ),
                {"tid": str(tid)},
            )
        session.commit()
        tid = str(tenants[0].id)
        plans: dict[str, str] = {}
        queries = {
            "list": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM estimates
                WHERE tenant_id = '{tid}' AND archived_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT 50
            """,
            "status": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM estimates
                WHERE tenant_id = '{tid}' AND status = 'APPROVED'
                ORDER BY created_at DESC LIMIT 50
            """,
            "history": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM estimate_status_history
                WHERE tenant_id = '{tid}'
                ORDER BY created_at ASC LIMIT 50
            """,
        }
        for name, sql in queries.items():
            rows = session.execute(text(sql)).fetchall()
            plans[name] = "\n".join(r[0] for r in rows)
            assert "Index" in plans[name] or "Seq Scan" in plans[name]
            print(f"\n=== EXPLAIN {name} ===\n{plans[name]}\n")
        n = session.execute(
            text("SELECT count(*) FROM estimates WHERE tenant_id = CAST(:tid AS uuid)"),
            {"tid": tid},
        ).scalar()
        assert n >= 2500
    finally:
        session.close()
