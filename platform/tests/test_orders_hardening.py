"""Phase 9 Orders hardening: snapshots, idempotency payload, money, archive."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.inventory import InventoryService
from callbot_platform.crm.orders import OrderService
from callbot_platform.crm.orders.constants import VALID_TRANSITIONS
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.inventory import InventoryBalance, InventoryTransaction
from callbot_platform.db.models.orders import OrderStatusHistory


def _setup(session: Session, tenant_id: uuid.UUID) -> dict:
    catalog = ProductCatalogService(session)
    prod = catalog.create(
        tenant_id,
        name="Gadget",
        sku="GAD-1",
        price="10.99",
        tax_rate="5",
        actor="t",
    )
    variant = catalog.variants.create(
        tenant_id,
        uuid.UUID(prod["id"]),
        sku="GAD-1-SM",
        price="12.50",
        actor="t",
    )
    inv = InventoryService(session)
    loc = inv.locations.create(
        tenant_id, name="Main", code="MAIN", actor="t", is_default=True
    )
    item = inv.items.ensure_for_variant(
        tenant_id, uuid.UUID(variant["id"]), actor="t"
    )
    inv.mutations.purchase(
        tenant_id,
        item.id,
        location_id=uuid.UUID(loc["id"]),
        quantity=200,
        actor="t",
    )
    customer = CustomerService(session).create(
        tenant_id, name="Buyer", phone="+15551008888", actor="t"
    )
    return {
        "product_id": uuid.UUID(prod["id"]),
        "variant_id": uuid.UUID(variant["id"]),
        "location_id": uuid.UUID(loc["id"]),
        "item_id": item.id,
        "customer_id": uuid.UUID(customer["id"]),
        "catalog": catalog,
    }


def test_idempotency_same_payload_returns_same_order(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = OrderService(session)
    body = {
        "customer_id": setup["customer_id"],
        "actor": "t",
        "items": [
            {
                "product_id": setup["product_id"],
                "variant_id": setup["variant_id"],
                "quantity": 2,
            }
        ],
        "idempotency_key": "hard-1",
    }
    a = api.create(tenant.id, **body)
    b = api.create(tenant.id, **body)
    assert a["id"] == b["id"]
    assert a["order_number"] == b["order_number"]


def test_idempotency_different_payload_rejected(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = OrderService(session)
    api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "product_id": setup["product_id"],
                "variant_id": setup["variant_id"],
                "quantity": 1,
            }
        ],
        idempotency_key="hard-2",
    )
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            items=[
                {
                    "product_id": setup["product_id"],
                    "variant_id": setup["variant_id"],
                    "quantity": 9,
                }
            ],
            idempotency_key="hard-2",
        )
    assert exc.value.code == "idempotency_conflict"


def test_historical_snapshots_survive_catalog_changes(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = OrderService(session)
    order = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "product_id": setup["product_id"],
                "variant_id": setup["variant_id"],
                "quantity": 1,
            }
        ],
    )
    setup["catalog"].update(
        tenant.id, setup["product_id"], name="Renamed Forever", actor="t"
    )
    setup["catalog"].update(
        tenant.id, setup["product_id"], price="999.00", actor="t"
    )
    got = api.get(tenant.id, uuid.UUID(order["id"]))
    assert got["items"][0]["product_name_snapshot"] == "Gadget"
    assert Decimal(got["items"][0]["unit_price"]) == Decimal("12.5000")


def test_money_precision_and_server_totals(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = OrderService(session)
    order = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "product_id": setup["product_id"],
                "variant_id": setup["variant_id"],
                "quantity": 3,
                "unit_price": "10.99",
                "discount_total": "0.10",
            }
        ],
        shipping_total="0.01",
        order_discount="0.01",
    )
    # 10.99*3=32.97; disc line 0.10 + order 0.01=0.11; tax 5% of 32.87=1.6435
    assert Decimal(order["subtotal"]) == Decimal("32.9700")
    assert Decimal(order["discount_total"]) == Decimal("0.1100")
    assert Decimal(order["tax_total"]) == Decimal("1.6435")
    assert Decimal(order["shipping_total"]) == Decimal("0.0100")
    assert Decimal(order["total"]) == Decimal("34.5135")


def test_invalid_transitions_no_history_or_inventory(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = OrderService(session)
    order = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "product_id": setup["product_id"],
                "variant_id": setup["variant_id"],
                "quantity": 1,
            }
        ],
        fulfillment_location_id=setup["location_id"],
    )
    oid = uuid.UUID(order["id"])
    for st in ("PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"):
        api.transition(tenant.id, oid, to_status=st, actor="t")
    before = list(
        session.scalars(
            select(OrderStatusHistory).where(OrderStatusHistory.order_id == oid)
        ).all()
    )
    bal = session.scalar(
        select(InventoryBalance).where(
            InventoryBalance.inventory_item_id == setup["item_id"]
        )
    )
    stock_before = bal.stock_quantity if bal else None
    for bad in ("PROCESSING", "CONFIRMED", "SHIPPED"):
        with pytest.raises(CrmError) as exc:
            api.transition(tenant.id, oid, to_status=bad, actor="t")
        assert exc.value.code == "invalid_transition"
    after = list(
        session.scalars(
            select(OrderStatusHistory).where(OrderStatusHistory.order_id == oid)
        ).all()
    )
    assert len(after) == len(before)
    session.refresh(bal)
    assert bal.stock_quantity == stock_before


def test_cancel_and_refund_idempotent(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = OrderService(session)
    order = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "product_id": setup["product_id"],
                "variant_id": setup["variant_id"],
                "quantity": 2,
            }
        ],
        fulfillment_location_id=setup["location_id"],
    )
    oid = uuid.UUID(order["id"])
    api.transition(tenant.id, oid, to_status="PENDING", actor="t")
    api.transition(tenant.id, oid, to_status="CONFIRMED", actor="t")
    api.transition(tenant.id, oid, to_status="CANCELLED", actor="t")
    api.transition(tenant.id, oid, to_status="CANCELLED", actor="t")
    releases = session.scalar(
        select(InventoryTransaction).where(
            InventoryTransaction.tenant_id == tenant.id,
            InventoryTransaction.idempotency_key
            == f"order:{oid}:release-cancel:{order['items'][0]['id']}",
        )
    )
    assert releases is not None
    release_count = len(
        list(
            session.scalars(
                select(InventoryTransaction).where(
                    InventoryTransaction.tenant_id == tenant.id,
                    InventoryTransaction.reference_id == str(oid),
                    InventoryTransaction.transaction_type == "RELEASE",
                )
            ).all()
        )
    )
    assert release_count == 1

    # Refund path
    order2 = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "product_id": setup["product_id"],
                "variant_id": setup["variant_id"],
                "quantity": 1,
            }
        ],
        fulfillment_location_id=setup["location_id"],
    )
    oid2 = uuid.UUID(order2["id"])
    for st in ("PENDING", "CONFIRMED", "PROCESSING", "SHIPPED", "DELIVERED"):
        api.transition(tenant.id, oid2, to_status=st, actor="t")
    api.transition(tenant.id, oid2, to_status="REFUNDED", actor="t")
    api.transition(tenant.id, oid2, to_status="REFUNDED", actor="t")
    returns = list(
        session.scalars(
            select(InventoryTransaction).where(
                InventoryTransaction.tenant_id == tenant.id,
                InventoryTransaction.reference_id == str(oid2),
                InventoryTransaction.transaction_type == "RETURN",
            )
        ).all()
    )
    assert len(returns) == 1


def test_confirmed_order_immutable_and_archive_blocks(
    session: Session, tenant: Tenant
) -> None:
    setup = _setup(session, tenant.id)
    api = OrderService(session)
    order = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "product_id": setup["product_id"],
                "variant_id": setup["variant_id"],
                "quantity": 1,
            }
        ],
        fulfillment_location_id=setup["location_id"],
    )
    oid = uuid.UUID(order["id"])
    api.transition(tenant.id, oid, to_status="PENDING", actor="t")
    api.transition(tenant.id, oid, to_status="CONFIRMED", actor="t")
    with pytest.raises(CrmError) as exc:
        api.update(
            tenant.id,
            oid,
            actor="t",
            items=[
                {
                    "product_id": setup["product_id"],
                    "variant_id": setup["variant_id"],
                    "quantity": 5,
                }
            ],
        )
    assert exc.value.code == "order_immutable"
    with pytest.raises(CrmError) as exc:
        api.update(
            tenant.id,
            oid,
            actor="t",
            shipping_address_snapshot={"line1": "x"},
        )
    assert exc.value.code == "order_immutable"
    # notes still allowed
    updated = api.update(tenant.id, oid, actor="t", notes="ops note")
    assert updated["notes"] == "ops note"

    api.transition(tenant.id, oid, to_status="CANCELLED", actor="t")
    api.archive(tenant.id, oid, actor="t")
    with pytest.raises(CrmError) as exc:
        api.transition(tenant.id, oid, to_status="PENDING", actor="t")
    assert exc.value.code == "order_archived"
    with pytest.raises(CrmError) as exc:
        api.update(tenant.id, oid, actor="t", notes="nope")
    assert exc.value.code == "order_archived"


def test_valid_transition_graph_complete() -> None:
    # Sanity: every documented edge exists; terminal states have no outbound except refund.
    asserted = {
        ("DRAFT", "PENDING"),
        ("DRAFT", "CANCELLED"),
        ("PENDING", "CONFIRMED"),
        ("PENDING", "CANCELLED"),
        ("CONFIRMED", "PROCESSING"),
        ("CONFIRMED", "CANCELLED"),
        ("PROCESSING", "SHIPPED"),
        ("PROCESSING", "CANCELLED"),
        ("SHIPPED", "DELIVERED"),
        ("SHIPPED", "CANCELLED"),
        ("DELIVERED", "REFUNDED"),
    }
    assert frozenset(asserted) == VALID_TRANSITIONS


def test_list_n_plus_one_bounded(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = OrderService(session)
    for _ in range(25):
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            items=[
                {
                    "product_id": setup["product_id"],
                    "variant_id": setup["variant_id"],
                    "quantity": 1,
                }
            ],
        )

    engine = session.get_bind()
    assert isinstance(engine, Engine)
    queries: list[str] = []

    def _count(conn, cursor, statement, parameters, context, executemany):
        queries.append(statement)

    event.listen(engine, "before_cursor_execute", _count)
    try:
        result = api.list(tenant.id, limit=20)
        assert len(result["orders"]) == 20
    finally:
        event.remove(engine, "before_cursor_execute", _count)

    # Bound: selectinload should keep statement count well below 1+N*items.
    assert len(queries) < 15, f"too many queries: {len(queries)}"


def test_keyset_pagination_stable(session: Session, tenant: Tenant) -> None:
    setup = _setup(session, tenant.id)
    api = OrderService(session)
    ids: list[str] = []
    for _ in range(7):
        row = api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            items=[
                {
                    "product_id": setup["product_id"],
                    "variant_id": setup["variant_id"],
                    "quantity": 1,
                }
            ],
        )
        ids.append(row["id"])
    page1 = api.list(tenant.id, limit=3)
    assert len(page1["orders"]) == 3
    assert page1["next_cursor"]
    page2 = api.list(tenant.id, limit=3, cursor=page1["next_cursor"])
    assert len(page2["orders"]) == 3
    page3 = api.list(tenant.id, limit=3, cursor=page2["next_cursor"])
    seen = [o["id"] for o in page1["orders"] + page2["orders"] + page3["orders"]]
    assert len(seen) == len(set(seen))
    assert set(seen) == set(ids)
