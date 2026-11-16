"""Phase 9 Orders: CRUD, money, lifecycle, inventory, isolation."""

from __future__ import annotations

import uuid
from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.customers.timeline import CustomerTimelineService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.inventory import InventoryService
from callbot_platform.crm.orders import OrderService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.inventory import InventoryBalance, InventoryTransaction
from callbot_platform.db.models.orders import OrderStatusHistory


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _catalog_setup(session: Session, tenant_id: uuid.UUID) -> dict:
    catalog = ProductCatalogService(session)
    prod = catalog.create(
        tenant_id,
        name="Widget",
        sku="WDG-1",
        price="25.00",
        tax_rate="10",
        actor="t",
    )
    variant = catalog.variants.create(
        tenant_id,
        uuid.UUID(prod["id"]),
        sku="WDG-1-BLU",
        price="30.00",
        actor="t",
    )
    inv = InventoryService(session)
    loc = inv.locations.create(
        tenant_id, name="Main", code="MAIN", actor="t", is_default=True
    )
    item = inv.items.ensure_for_variant(tenant_id, uuid.UUID(variant["id"]), actor="t")
    inv.mutations.purchase(
        tenant_id,
        item.id,
        location_id=uuid.UUID(loc["id"]),
        quantity=100,
        actor="t",
    )
    customer = CustomerService(session).create(
        tenant_id, name="Buyer", phone="+15551009999", actor="t"
    )
    return {
        "product_id": uuid.UUID(prod["id"]),
        "variant_id": uuid.UUID(variant["id"]),
        "location_id": uuid.UUID(loc["id"]),
        "item_id": item.id,
        "customer_id": uuid.UUID(customer["id"]),
    }


def test_order_crud_money_search_archive(session: Session, tenant: Tenant) -> None:
    setup = _catalog_setup(session, tenant.id)
    api = OrderService(session)
    created = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "product_id": setup["product_id"],
                "variant_id": setup["variant_id"],
                "quantity": 2,
                "discount_total": "1.00",
            }
        ],
        shipping_total="5.00",
        order_discount="2.00",
        currency="USD",
        notes="rush",
        fulfillment_location_id=setup["location_id"],
    )
    assert created["order_number"] == "ORD-000001"
    assert created["status"] == "DRAFT"
    assert created["currency"] == "USD"
    # unit 30 * 2 = 60; disc 1; tax 10% of 59 = 5.9; + ship 5 - order disc 2
    assert Decimal(created["subtotal"]) == Decimal("60.0000")
    assert Decimal(created["discount_total"]) == Decimal("3.0000")
    assert Decimal(created["tax_total"]) == Decimal("5.9000")
    assert Decimal(created["shipping_total"]) == Decimal("5.0000")
    assert Decimal(created["total"]) == Decimal("67.9000")
    assert len(created["items"]) == 1
    assert created["items"][0]["sku_snapshot"] == "WDG-1-BLU"
    assert created["items"][0]["product_name_snapshot"] == "Widget"

    found = api.list(tenant.id, q="ORD-000001")
    assert len(found["orders"]) == 1
    found = api.list(tenant.id, status="DRAFT", customer_id=setup["customer_id"])
    assert len(found["orders"]) == 1
    found = api.list(tenant.id, sku="WDG-1-BLU")
    assert len(found["orders"]) == 1
    found = api.list(tenant.id, product_id=setup["product_id"])
    assert len(found["orders"]) == 1

    updated = api.update(
        tenant.id,
        uuid.UUID(created["id"]),
        notes="updated notes",
        actor="t",
    )
    assert updated["notes"] == "updated notes"

    archived = api.archive(tenant.id, uuid.UUID(created["id"]), actor="t")
    assert archived["archived_at"] is not None
    restored = api.restore(tenant.id, uuid.UUID(created["id"]), actor="t")
    assert restored["archived_at"] is None


def test_idempotent_create_and_snapshot_immutability(
    session: Session, tenant: Tenant
) -> None:
    setup = _catalog_setup(session, tenant.id)
    api = OrderService(session)
    a = api.create(
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
        idempotency_key="idem-1",
    )
    b = api.create(
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
        idempotency_key="idem-1",
    )
    assert a["id"] == b["id"]

    # Catalog price change must not rewrite historical line.
    catalog = ProductCatalogService(session)
    catalog.update(
        tenant.id,
        setup["product_id"],
        name="Widget Renamed",
        actor="t",
    )
    got = api.get(tenant.id, uuid.UUID(a["id"]))
    assert got["items"][0]["product_name_snapshot"] == "Widget"
    assert Decimal(got["items"][0]["unit_price"]) == Decimal("30.0000")


def test_status_machine_and_history(session: Session, tenant: Tenant) -> None:
    setup = _catalog_setup(session, tenant.id)
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

    with pytest.raises(CrmError) as exc:
        api.update(tenant.id, oid, status="CONFIRMED", actor="t")
    assert exc.value.code == "use_transition"

    with pytest.raises(CrmError) as exc:
        api.transition(tenant.id, oid, to_status="SHIPPED", actor="t")
    assert exc.value.code == "invalid_transition"
    rows = list(
        session.scalars(
            select(OrderStatusHistory).where(OrderStatusHistory.order_id == oid)
        ).all()
    )
    assert len(rows) == 1

    api.transition(tenant.id, oid, to_status="PENDING", actor="t")
    api.transition(tenant.id, oid, to_status="CONFIRMED", actor="t")
    # Immutable after confirm
    with pytest.raises(CrmError) as exc:
        api.update(
            tenant.id,
            oid,
            items=[
                {
                    "product_id": setup["product_id"],
                    "variant_id": setup["variant_id"],
                    "quantity": 9,
                }
            ],
            actor="t",
        )
    assert exc.value.code == "order_immutable"

    api.transition(tenant.id, oid, to_status="PROCESSING", actor="t")
    api.transition(tenant.id, oid, to_status="SHIPPED", actor="t")
    api.transition(tenant.id, oid, to_status="DELIVERED", actor="t")
    refunded = api.transition(tenant.id, oid, to_status="REFUNDED", actor="t")
    assert refunded["status"] == "REFUNDED"
    history = api.history(tenant.id, oid)["history"]
    assert any(h["to_status"] == "REFUNDED" for h in history)


def test_inventory_reserve_consume_cancel(session: Session, tenant: Tenant) -> None:
    setup = _catalog_setup(session, tenant.id)
    api = OrderService(session)
    order = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "product_id": setup["product_id"],
                "variant_id": setup["variant_id"],
                "quantity": 5,
            }
        ],
        fulfillment_location_id=setup["location_id"],
    )
    oid = uuid.UUID(order["id"])
    api.transition(tenant.id, oid, to_status="PENDING", actor="t")
    api.transition(tenant.id, oid, to_status="CONFIRMED", actor="t")

    bal = session.scalar(
        select(InventoryBalance).where(
            InventoryBalance.tenant_id == tenant.id,
            InventoryBalance.inventory_item_id == setup["item_id"],
            InventoryBalance.location_id == setup["location_id"],
        )
    )
    assert bal is not None
    assert bal.reserved_quantity == 5
    assert bal.stock_quantity == 100

    # Duplicate confirm is no-op (same status).
    api.transition(tenant.id, oid, to_status="CONFIRMED", actor="t")
    assert bal.reserved_quantity == 5

    cancelled = api.transition(tenant.id, oid, to_status="CANCELLED", actor="t")
    assert cancelled["status"] == "CANCELLED"
    session.refresh(bal)
    assert bal.reserved_quantity == 0
    assert bal.stock_quantity == 100

    # Idempotent cancel inventory release
    txs = list(
        session.scalars(
            select(InventoryTransaction).where(
                InventoryTransaction.tenant_id == tenant.id,
                InventoryTransaction.idempotency_key.like(f"order:{oid}:%"),
            )
        ).all()
    )
    assert any(t.transaction_type == "RESERVATION" for t in txs)
    assert any(t.transaction_type == "RELEASE" for t in txs)


def test_inventory_processing_sale_and_refund_return(
    session: Session, tenant: Tenant
) -> None:
    setup = _catalog_setup(session, tenant.id)
    api = OrderService(session)
    order = api.create(
        tenant.id,
        customer_id=setup["customer_id"],
        actor="t",
        items=[
            {
                "product_id": setup["product_id"],
                "variant_id": setup["variant_id"],
                "quantity": 4,
            }
        ],
        fulfillment_location_id=setup["location_id"],
    )
    oid = uuid.UUID(order["id"])
    for st in ("PENDING", "CONFIRMED", "PROCESSING"):
        api.transition(tenant.id, oid, to_status=st, actor="t")

    bal = session.scalar(
        select(InventoryBalance).where(
            InventoryBalance.tenant_id == tenant.id,
            InventoryBalance.inventory_item_id == setup["item_id"],
        )
    )
    assert bal is not None
    assert bal.stock_quantity == 96
    assert bal.reserved_quantity == 0

    for st in ("SHIPPED", "DELIVERED", "REFUNDED"):
        api.transition(tenant.id, oid, to_status=st, actor="t")
    session.refresh(bal)
    assert bal.stock_quantity == 100


def test_cross_tenant_isolation(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    setup_a = _catalog_setup(session, tenant.id)
    setup_b = _catalog_setup(session, tenant_b.id)
    api = OrderService(session)
    order = api.create(
        tenant.id,
        customer_id=setup_a["customer_id"],
        actor="t",
        items=[
            {
                "product_id": setup_a["product_id"],
                "variant_id": setup_a["variant_id"],
                "quantity": 1,
            }
        ],
    )
    oid = uuid.UUID(order["id"])
    with pytest.raises(CrmError):
        api.get(tenant_b.id, oid)
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup_b["customer_id"],
            actor="t",
            items=[
                {
                    "product_id": setup_a["product_id"],
                    "variant_id": setup_a["variant_id"],
                    "quantity": 1,
                }
            ],
        )
    assert exc.value.code == "customer_not_found"
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup_a["customer_id"],
            actor="t",
            items=[
                {
                    "product_id": setup_b["product_id"],
                    "variant_id": setup_b["variant_id"],
                    "quantity": 1,
                }
            ],
        )
    assert exc.value.code == "product_not_found"


def test_variant_product_mismatch(session: Session, tenant: Tenant) -> None:
    setup = _catalog_setup(session, tenant.id)
    catalog = ProductCatalogService(session)
    other = catalog.create(tenant.id, name="Other", sku="OTH-1", price="5", actor="t")
    api = OrderService(session)
    with pytest.raises(CrmError) as exc:
        api.create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            items=[
                {
                    "product_id": uuid.UUID(other["id"]),
                    "variant_id": setup["variant_id"],
                    "quantity": 1,
                }
            ],
        )
    assert exc.value.code == "variant_product_mismatch"


def test_customer_timeline_order_events(session: Session, tenant: Tenant) -> None:
    setup = _catalog_setup(session, tenant.id)
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

    timeline = CustomerTimelineService(session).get_timeline(
        tenant.id,
        setup["customer_id"],
        allowed_types=frozenset({"ORDER"}),
    )
    types = {i["metadata"].get("event") for i in timeline["items"]}
    assert "ORDER_CREATED" in types
    assert "ORDER_CONFIRMED" in types
