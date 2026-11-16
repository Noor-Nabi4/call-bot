"""PostgreSQL concurrency for invoice numbering."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.invoices import InvoiceService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import Base, Tenant
from callbot_platform.db.models.invoices import Invoice

PG_URL = os.environ.get(
    "INVOICES_PG_TEST_URL",
    os.environ.get(
        "ESTIMATES_PG_TEST_URL",
        "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
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
    not _PG_UP, reason="PostgreSQL not available for invoice PG tests"
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


def _tenant(session: Session) -> Tenant:
    row = Tenant(name="Inv PG", slug=f"inv-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def test_concurrent_invoice_numbering(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        customer = CustomerService(session).create(
            tenant.id,
            name="Buyer",
            phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
            actor="setup",
        )
        prod = ProductCatalogService(session).create(
            tenant.id,
            name="W",
            sku=f"S-{uuid.uuid4().hex[:6]}",
            price="1.00",
            actor="setup",
        )
        session.commit()
        tenant_id = tenant.id
        customer_id = uuid.UUID(customer["id"])
        product_id = uuid.UUID(prod["id"])
    finally:
        session.close()

    def worker(_: int) -> str:
        s = pg_factory()
        try:
            row = InvoiceService(s).create(
                tenant_id,
                customer_id=customer_id,
                actor="w",
                items=[
                    {
                        "item_type": "PRODUCT",
                        "product_id": product_id,
                        "quantity": 1,
                    }
                ],
            )
            s.commit()
            return row["invoice_number"]
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        numbers = list(pool.map(worker, range(8)))

    assert len(set(numbers)) == 8
    s = pg_factory()
    try:
        count = s.scalar(
            select(Invoice).where(Invoice.tenant_id == tenant_id)
        )
        assert count is not None
    finally:
        s.close()
