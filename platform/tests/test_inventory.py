"""Phase 6 Inventory: transactions, isolation, idempotency, alerts."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.inventory import InventoryService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db.models import NotificationOutbox, Tenant
from callbot_platform.db.models.inventory import (
    InventoryAlertEvent,
    InventoryBalance,
    InventoryTransaction,
)


@pytest.fixture()
def tenant_b(session: Session) -> Tenant:
    row = Tenant(name="Other Co", slug=f"other-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _setup_variant(session: Session, tenant_id: uuid.UUID) -> tuple[uuid.UUID, uuid.UUID]:
    catalog = ProductCatalogService(session)
    prod = catalog.create(tenant_id, name="Valve", sku="VLV-1", price="10", actor="t")
    variant = catalog.variants.create(
        tenant_id,
        uuid.UUID(prod["id"]),
        sku="VLV-1-RED",
        actor="t",
    )
    inv = InventoryService(session)
    loc = inv.locations.create(
        tenant_id, name="Main", code="MAIN", actor="t", is_default=True
    )
    item = inv.items.ensure_for_variant(
        tenant_id, uuid.UUID(variant["id"]), actor="t"
    )
    return item.id, uuid.UUID(loc["id"])


def test_transactions_and_constraints(session: Session, tenant: Tenant) -> None:
    item_id, loc_id = _setup_variant(session, tenant.id)
    inv = InventoryService(session)
    inv.mutations.purchase(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=10,
        actor="tester",
    )
    inv.mutations.reserve(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=3,
        actor="tester",
    )
    avail = inv.check_available_quantity(
        tenant.id, inventory_item_id=item_id, location_id=loc_id
    )
    assert avail["available_quantity"] == 7
    inv.mutations.sale(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=7,
        actor="tester",
    )
    with pytest.raises(CrmError) as exc:
        inv.mutations.sale(
            tenant.id,
            item_id,
            location_id=loc_id,
            quantity=1,
            actor="tester",
        )
    assert exc.value.code == "insufficient_stock"
    inv.mutations.release(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=3,
        actor="tester",
    )
    inv.mutations.adjust(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=-2,
        actor="tester",
        reason="cycle count",
    )
    bal = session.scalar(
        select(InventoryBalance).where(
            InventoryBalance.tenant_id == tenant.id,
            InventoryBalance.inventory_item_id == item_id,
        )
    )
    assert bal is not None
    assert bal.stock_quantity == 1
    assert bal.reserved_quantity == 0


def test_idempotency(session: Session, tenant: Tenant) -> None:
    item_id, loc_id = _setup_variant(session, tenant.id)
    inv = InventoryService(session)
    r1 = inv.mutations.purchase(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=5,
        actor="tester",
        idempotency_key="purchase-abc",
    )
    r2 = inv.mutations.purchase(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=5,
        actor="tester",
        idempotency_key="purchase-abc",
    )
    assert r2["idempotent"] is True
    assert r1["transaction"]["id"] == r2["transaction"]["id"]
    count = session.scalar(
        select(func.count())
        .select_from(InventoryTransaction)
        .where(InventoryTransaction.tenant_id == tenant.id)
    )
    assert int(count or 0) == 1


def test_tenant_isolation(
    session: Session, tenant: Tenant, tenant_b: Tenant
) -> None:
    item_id, loc_id = _setup_variant(session, tenant.id)
    inv_b = InventoryService(session)
    with pytest.raises(CrmError):
        inv_b.mutations.purchase(
            tenant_b.id,
            item_id,
            location_id=loc_id,
            quantity=1,
            actor="attacker",
        )


def test_low_stock_alert_transition(session: Session, tenant: Tenant) -> None:
    tenant.email = "ops@example.com"
    session.flush()
    item_id, loc_id = _setup_variant(session, tenant.id)
    inv = InventoryService(session)
    inv.set_minimum_stock(
        tenant.id,
        item_id,
        location_id=loc_id,
        minimum_stock=5,
        actor="tester",
    )
    inv.mutations.purchase(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=10,
        actor="tester",
    )
    inv.mutations.sale(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=6,
        actor="tester",
    )
    events = list(
        session.scalars(
            select(InventoryAlertEvent).where(
                InventoryAlertEvent.tenant_id == tenant.id
            )
        ).all()
    )
    assert any(e.alert_type == "LOW_STOCK" for e in events)
    from callbot_platform.db.models.inventory import InventoryOutboxEvent

    alert_outbox = list(
        session.scalars(
            select(InventoryOutboxEvent).where(
                InventoryOutboxEvent.tenant_id == tenant.id,
                InventoryOutboxEvent.event_type == "INVENTORY_LOW_STOCK",
            )
        ).all()
    )
    assert len(alert_outbox) == 1
    assert alert_outbox[0].status == "pending"
    # Email is enqueued by inventory outbox worker, not the mutation TX.
    notif_before = list(
        session.scalars(
            select(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant.id)
        ).all()
    )
    assert notif_before == []
    inv.mutations.sale(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=4,
        actor="tester",
    )
    events2 = list(
        session.scalars(
            select(InventoryAlertEvent).where(
                InventoryAlertEvent.tenant_id == tenant.id,
                InventoryAlertEvent.alert_type == "LOW_STOCK",
            )
        ).all()
    )
    assert len(events2) == 1


def test_concurrent_sales(session: Session, tenant: Tenant) -> None:
    item_id, loc_id = _setup_variant(session, tenant.id)
    inv = InventoryService(session)
    inv.mutations.purchase(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=10,
        actor="tester",
    )
    inv.mutations.sale(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=7,
        actor="a",
        idempotency_key="c1",
    )
    with pytest.raises(CrmError) as exc:
        inv.mutations.sale(
            tenant.id,
            item_id,
            location_id=loc_id,
            quantity=7,
            actor="b",
            idempotency_key="c2",
        )
    assert exc.value.code == "insufficient_stock"
    bal = session.scalar(
        select(InventoryBalance).where(
            InventoryBalance.inventory_item_id == item_id,
        )
    )
    assert bal is not None
    assert bal.stock_quantity >= 0
    assert bal.reserved_quantity <= bal.stock_quantity


def test_variant_create_auto_provisions_inventory_item(
    session: Session, tenant: Tenant
) -> None:
    catalog = ProductCatalogService(session)
    prod = catalog.create(tenant.id, name="Auto", sku="AUTO-1", price="1", actor="t")
    variant = catalog.variants.create(
        tenant.id, uuid.UUID(prod["id"]), sku="AUTO-1-A", actor="t"
    )
    assert variant["inventory_item_id"]
    item_id = uuid.UUID(variant["inventory_item_id"])
    inv = InventoryService(session)
    again = inv.items.ensure_for_variant(
        tenant.id, uuid.UUID(variant["id"]), actor="t"
    )
    assert again.id == item_id
    report = inv.items.backfill_missing_for_tenant(tenant.id)
    assert report["created"] == 0
    assert report["already_existing"] >= 1


def test_location_archive_guard(session: Session, tenant: Tenant) -> None:
    item_id, loc_id = _setup_variant(session, tenant.id)
    inv = InventoryService(session)
    inv.mutations.purchase(
        tenant.id,
        item_id,
        location_id=loc_id,
        quantity=2,
        actor="tester",
    )
    with pytest.raises(CrmError) as exc:
        inv.locations.archive(tenant.id, loc_id, actor="tester")
    assert exc.value.code == "location_has_stock"
