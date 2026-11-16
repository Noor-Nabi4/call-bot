"""PostgreSQL concurrency tests for Phase 7 pricebook effective ranges.

Skip when Postgres is unavailable — SQLite cannot prove exclusion/FOR UPDATE races.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import UTC, datetime

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.services import ServicesPricebookService
from callbot_platform.db.models import Base, Tenant
from callbot_platform.db.models.services import (
    Pricebook,
    PricebookItem,
    PricebookOverride,
)

PG_URL = os.environ.get(
    "SERVICES_PG_TEST_URL",
    os.environ.get(
        "INVENTORY_PG_TEST_URL",
        "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
    ),
)

_EXCLUSION_SQL = (
    "CREATE EXTENSION IF NOT EXISTS btree_gist",
    """
    ALTER TABLE pricebook_items
    ADD CONSTRAINT excl_pricebook_items_active_effective
    EXCLUDE USING gist (
        tenant_id WITH =,
        pricebook_id WITH =,
        service_id WITH =,
        tstzrange(
            COALESCE(effective_from, '-infinity'::timestamptz),
            COALESCE(effective_until, 'infinity'::timestamptz),
            '[]'
        ) WITH &&
    )
    WHERE (archived_at IS NULL AND status = 'ACTIVE')
    """,
    """
    ALTER TABLE pricebook_overrides
    ADD CONSTRAINT excl_pricebook_overrides_active_effective
    EXCLUDE USING gist (
        tenant_id WITH =,
        pricebook_id WITH =,
        service_id WITH =,
        tstzrange(
            COALESCE(effective_from, '-infinity'::timestamptz),
            COALESCE(effective_until, 'infinity'::timestamptz),
            '[]'
        ) WITH &&
    )
    WHERE (archived_at IS NULL AND status = 'ACTIVE')
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS uq_pricebooks_tenant_one_default
    ON pricebooks (tenant_id)
    WHERE is_default = true AND archived_at IS NULL
    """,
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
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        for stmt in _EXCLUSION_SQL:
            conn.execute(text(stmt))
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def _seed_scope(
    factory: sessionmaker[Session],
) -> tuple[uuid.UUID, uuid.UUID, uuid.UUID]:
    session = factory()
    try:
        tenant = Tenant(name="PG Price", slug=f"pgpb-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        api = ServicesPricebookService(session)
        svc = api.create_service(
            tenant.id,
            name="AC Tune-Up",
            code=f"AC-{uuid.uuid4().hex[:6]}",
            base_price="100",
            actor="seed",
        )
        pb = api.pricebooks.create(
            tenant.id, name="Standard", is_default=True, actor="seed"
        )
        session.commit()
        return tenant.id, uuid.UUID(svc["id"]), uuid.UUID(pb["id"])
    finally:
        session.close()


def test_pg_concurrent_overlapping_items(pg_factory: sessionmaker[Session]) -> None:
    tenant_id, service_id, pricebook_id = _seed_scope(pg_factory)

    def _create(price: str, start: datetime, end: datetime, key: str) -> str:
        db = pg_factory()
        try:
            api = ServicesPricebookService(db)
            api.pricebooks.create_item(
                tenant_id,
                pricebook_id,
                service_id=service_id,
                pricing_type="FIXED",
                price=price,
                effective_from=start,
                effective_until=end,
                actor=key,
            )
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

    a_from = datetime(2027, 1, 1, tzinfo=UTC)
    a_until = datetime(2027, 6, 30, tzinfo=UTC)
    b_from = datetime(2027, 5, 1, tzinfo=UTC)
    b_until = datetime(2027, 12, 31, tzinfo=UTC)

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [
            pool.submit(_create, "149", a_from, a_until, "a"),
            pool.submit(_create, "179", b_from, b_until, "b"),
        ]
        results = [f.result() for f in as_completed(futs)]

    assert results.count("ok") == 1
    assert "effective_overlap" in results

    session = pg_factory()
    try:
        rows = list(
            session.scalars(
                select(PricebookItem).where(
                    PricebookItem.tenant_id == tenant_id,
                    PricebookItem.pricebook_id == pricebook_id,
                    PricebookItem.service_id == service_id,
                    PricebookItem.archived_at.is_(None),
                    PricebookItem.status == "ACTIVE",
                )
            ).all()
        )
        assert len(rows) == 1
    finally:
        session.close()


def test_pg_concurrent_overlapping_overrides(pg_factory: sessionmaker[Session]) -> None:
    tenant_id, service_id, pricebook_id = _seed_scope(pg_factory)
    session = pg_factory()
    try:
        api = ServicesPricebookService(session)
        api.pricebooks.create_item(
            tenant_id,
            pricebook_id,
            service_id=service_id,
            pricing_type="FIXED",
            price="120",
            actor="seed",
        )
        session.commit()
    finally:
        session.close()

    def _ov(price: str, start: datetime, end: datetime, key: str) -> str:
        db = pg_factory()
        try:
            api = ServicesPricebookService(db)
            api.pricebooks.create_override(
                tenant_id,
                pricebook_id,
                service_id=service_id,
                override_price=price,
                effective_from=start,
                effective_until=end,
                actor=key,
            )
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

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [
            pool.submit(
                _ov,
                "110",
                datetime(2027, 1, 1, tzinfo=UTC),
                datetime(2027, 6, 30, tzinfo=UTC),
                "a",
            ),
            pool.submit(
                _ov,
                "105",
                datetime(2027, 4, 1, tzinfo=UTC),
                datetime(2027, 12, 31, tzinfo=UTC),
                "b",
            ),
        ]
        results = [f.result() for f in as_completed(futs)]

    assert results.count("ok") == 1
    session = pg_factory()
    try:
        count = len(
            list(
                session.scalars(
                    select(PricebookOverride).where(
                        PricebookOverride.tenant_id == tenant_id,
                        PricebookOverride.archived_at.is_(None),
                        PricebookOverride.status == "ACTIVE",
                    )
                ).all()
            )
        )
        assert count == 1
    finally:
        session.close()


def test_pg_concurrent_default_pricebook(pg_factory: sessionmaker[Session]) -> None:
    session = pg_factory()
    try:
        tenant = Tenant(name="Defaults", slug=f"def-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        api = ServicesPricebookService(session)
        a = api.pricebooks.create(tenant.id, name="A", is_default=False, actor="s")
        b = api.pricebooks.create(tenant.id, name="B", is_default=False, actor="s")
        session.commit()
        tenant_id = tenant.id
        a_id = uuid.UUID(a["id"])
        b_id = uuid.UUID(b["id"])
    finally:
        session.close()

    def _set_default(pb_id: uuid.UUID, key: str) -> str:
        db = pg_factory()
        try:
            api = ServicesPricebookService(db)
            api.pricebooks.update(tenant_id, pb_id, is_default=True, actor=key)
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

    with ThreadPoolExecutor(max_workers=2) as pool:
        futs = [
            pool.submit(_set_default, a_id, "a"),
            pool.submit(_set_default, b_id, "b"),
        ]
        results = [f.result() for f in as_completed(futs)]

    assert all(
        r in {"ok", "default_conflict", "conflict"} or r.startswith("error:")
        for r in results
    )
    session = pg_factory()
    try:
        defaults = list(
            session.scalars(
                select(Pricebook).where(
                    Pricebook.tenant_id == tenant_id,
                    Pricebook.is_default.is_(True),
                    Pricebook.archived_at.is_(None),
                )
            ).all()
        )
        assert len(defaults) == 1
    finally:
        session.close()
