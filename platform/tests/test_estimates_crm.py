"""Phase 13 Estimates: lifecycle, money, conversion, isolation."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.estimates import EstimateService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.estimates import EstimateStatusHistory
from callbot_platform.db.models.jobs import Job
from callbot_platform.db.models.orders import Order


def _setup(session: Session, tenant_id: uuid.UUID) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Buyer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="t",
    )
    catalog = ProductCatalogService(session)
    prod = catalog.create(
        tenant_id,
        name="Widget",
        sku=f"W-{uuid.uuid4().hex[:6]}",
        price="25.00",
        tax_rate="10",
        actor="t",
    )
    svc = ServicesPricebookService(session).create_service(
        tenant_id,
        name="Repair",
        actor="t",
        duration_minutes=60,
        base_price="100.00",
    )
    return {
        "customer_id": uuid.UUID(customer["id"]),
        "product_id": uuid.UUID(prod["id"]),
        "service_id": uuid.UUID(svc["id"]),
    }


def test_estimate_create_money_lifecycle_convert_job(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = EstimateService(session)
    created = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        title="HVAC quote",
        items=[
            {
                "item_type": "SERVICE",
                "service_id": setup["service_id"],
                "quantity": "2",
            },
            {
                "item_type": "PRODUCT",
                "product_id": setup["product_id"],
                "quantity": 1,
            },
            {
                "item_type": "CUSTOM",
                "name": "Travel",
                "unit_price": "15.00",
                "quantity": "1",
            },
        ],
        estimate_discount="5.00",
        valid_until=datetime.now(UTC) + timedelta(days=14),
    )
    assert created["estimate_number"] == "EST-000001"
    assert created["status"] == "DRAFT"
    assert Decimal(created["subtotal"]) == Decimal("240.0000")
    assert Decimal(created["discount_total"]) == Decimal("5.0000")
    assert Decimal(created["tax_total"]) == Decimal("2.5000")
    assert Decimal(created["total"]) == Decimal("237.5000")
    assert len(created["items"]) == 3

    eid = uuid.UUID(created["id"])
    sent = api.send(tenant.id, eid, actor="t")
    assert sent["status"] == "SENT"
    approved = api.approve(tenant.id, eid, actor="t")
    assert approved["status"] == "APPROVED"

    conv = api.convert(tenant.id, eid, actor="t", target_type="JOB")
    assert conv["already_converted"] is False
    assert conv["estimate"]["status"] == "CONVERTED"
    job = session.scalar(
        select(Job).where(Job.id == uuid.UUID(conv["conversion"]["target_id"]))
    )
    assert job is not None
    assert job.customer_id == setup["customer_id"]

    again = api.convert(tenant.id, eid, actor="t", target_type="JOB")
    assert again["already_converted"] is True


def test_estimate_reject_expire_and_price_snapshot(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = EstimateService(session)
    created = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "item_type": "PRODUCT",
                "product_id": setup["product_id"],
                "quantity": 2,
            }
        ],
    )
    eid = uuid.UUID(created["id"])
    unit = created["items"][0]["unit_price"]
    ProductCatalogService(session).update(
        tenant.id, setup["product_id"], actor="t", price="999.00"
    )
    got = api.get(tenant.id, eid)
    assert got["items"][0]["unit_price"] == unit

    api.send(tenant.id, eid, actor="t")
    rejected = api.reject(tenant.id, eid, actor="t", reason="too expensive")
    assert rejected["status"] == "REJECTED"

    expired = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "item_type": "CUSTOM",
                "name": "X",
                "unit_price": "1.00",
                "quantity": "1",
            }
        ],
        valid_until=datetime.now(UTC) - timedelta(hours=1),
    )
    api.send(tenant.id, uuid.UUID(expired["id"]), actor="t")
    with pytest.raises(CrmError) as exc:
        api.approve(tenant.id, uuid.UUID(expired["id"]), actor="t")
    assert exc.value.code == "estimate_expired"


def test_convert_to_order_and_idempotency(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = EstimateService(session)
    created = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "item_type": "PRODUCT",
                "product_id": setup["product_id"],
                "quantity": 3,
            }
        ],
        idempotency_key="est-create-1",
    )
    again = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "item_type": "PRODUCT",
                "product_id": setup["product_id"],
                "quantity": 3,
            }
        ],
        idempotency_key="est-create-1",
    )
    assert again["id"] == created["id"]

    eid = uuid.UUID(created["id"])
    api.send(tenant.id, eid, actor="t")
    api.approve(tenant.id, eid, actor="t")
    conv = api.convert(
        tenant.id,
        eid,
        actor="t",
        target_type="ORDER",
        idempotency_key="conv-1",
    )
    assert conv["conversion"]["target_type"] == "ORDER"
    order = session.scalar(
        select(Order).where(Order.id == uuid.UUID(conv["conversion"]["target_id"]))
    )
    assert order is not None
    assert order.customer_id == setup["customer_id"]

    with pytest.raises(CrmError) as exc:
        api.convert(
            tenant.id,
            eid,
            actor="t",
            target_type="JOB",
            idempotency_key="conv-1",
        )
    assert exc.value.code == "idempotency_conflict"


def test_cross_tenant_isolation(session: Session, tenant: Tenant) -> None:
    other = Tenant(name="Other", slug=f"o-{uuid.uuid4().hex[:8]}")
    session.add(other)
    session.flush()
    setup_a = _setup(session, tenant.id)
    setup_b = _setup(session, other.id)
    api = EstimateService(session)
    est = api.create(
        tenant.id,
        customer_id=setup_a["customer_id"],
        actor="t",
        items=[
            {
                "item_type": "CUSTOM",
                "name": "A",
                "unit_price": "10",
                "quantity": "1",
            }
        ],
    )
    with pytest.raises(CrmError):
        api.get(other.id, uuid.UUID(est["id"]))
    with pytest.raises(CrmError):
        api.create(
            tenant.id,
            customer_id=setup_b["customer_id"],
            actor="t",
            items=[
                {
                    "item_type": "CUSTOM",
                    "name": "X",
                    "unit_price": "1",
                    "quantity": "1",
                }
            ],
        )


def test_invalid_transition_no_history_noise(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = EstimateService(session)
    est = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "item_type": "CUSTOM",
                "name": "A",
                "unit_price": "10",
                "quantity": "1",
            }
        ],
    )
    eid = uuid.UUID(est["id"])
    n0 = session.scalar(
        select(EstimateStatusHistory).where(EstimateStatusHistory.estimate_id == eid)
    )
    assert n0 is not None
    with pytest.raises(CrmError) as exc:
        api.approve(tenant.id, eid, actor="t")
    assert exc.value.code == "invalid_transition"
    hist = list(
        session.scalars(
            select(EstimateStatusHistory).where(
                EstimateStatusHistory.estimate_id == eid
            )
        ).all()
    )
    assert len(hist) == 1


def test_list_n_plus_one_bounded(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = EstimateService(session)
    for i in range(20):
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            items=[
                {
                    "item_type": "CUSTOM",
                    "name": f"Line {i}",
                    "unit_price": "1.00",
                    "quantity": "1",
                }
            ],
        )
    engine: Engine = session.get_bind()
    queries: list[str] = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        result = api.list(tenant.id, limit=50)
        assert len(result["estimates"]) >= 20
    finally:
        event.remove(engine, "before_cursor_execute", _count)
    assert len(queries) < 15, f"too many queries: {len(queries)}"
