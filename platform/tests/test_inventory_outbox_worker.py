"""Inventory outbox worker: claim, process, retry, idempotency."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.config import Settings
from callbot_platform.crm.inventory import InventoryService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db import get_session_factory
from callbot_platform.db.models import NotificationOutbox, Tenant
from callbot_platform.db.models.inventory import (
    InventoryAlertEvent,
    InventoryOutboxEvent,
)
from callbot_platform.workers.inventory_outbox import (
    STATUS_DEAD,
    STATUS_PENDING,
    STATUS_PROCESSED,
    InventoryOutboxWorker,
)


def _seed(session: Session, tenant: Tenant) -> tuple[uuid.UUID, uuid.UUID]:
    tenant.email = "ops@example.com"
    session.flush()
    catalog = ProductCatalogService(session)
    prod = catalog.create(tenant.id, name="Widget", sku="W-1", price="10", actor="t")
    variant = catalog.variants.create(
        tenant.id, uuid.UUID(prod["id"]), sku="W-1-A", actor="t"
    )
    inv = InventoryService(session)
    loc = inv.locations.create(
        tenant.id, name="Main", code="MAIN", actor="t", is_default=True
    )
    item = inv.items.ensure_for_variant(
        tenant.id, uuid.UUID(variant["id"]), actor="t"
    )
    inv.set_minimum_stock(
        tenant.id,
        item.id,
        location_id=uuid.UUID(loc["id"]),
        minimum_stock=5,
        actor="t",
    )
    inv.mutations.purchase(
        tenant.id,
        item.id,
        location_id=uuid.UUID(loc["id"]),
        quantity=10,
        actor="t",
    )
    inv.mutations.sale(
        tenant.id,
        item.id,
        location_id=uuid.UUID(loc["id"]),
        quantity=6,
        actor="t",
    )
    session.commit()
    return item.id, uuid.UUID(loc["id"])


def test_inventory_outbox_processes_low_stock_to_notification(
    session: Session, tenant: Tenant
) -> None:
    _seed(session, tenant)
    pending = list(
        session.scalars(
            select(InventoryOutboxEvent).where(
                InventoryOutboxEvent.tenant_id == tenant.id,
                InventoryOutboxEvent.event_type == "INVENTORY_LOW_STOCK",
                InventoryOutboxEvent.status == STATUS_PENDING,
            )
        ).all()
    )
    assert len(pending) == 1

    worker = InventoryOutboxWorker(
        get_session_factory(),
        settings=Settings(outbox_batch_size=10, outbox_max_retries=3),
    )
    n = worker.process_batch()
    assert n >= 1

    session.expire_all()
    row = session.get(InventoryOutboxEvent, pending[0].id)
    assert row is not None
    assert row.status == STATUS_PROCESSED
    assert row.processed_at is not None

    notifs = list(
        session.scalars(
            select(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant.id)
        ).all()
    )
    assert any(o.channel == "email" for o in notifs)
    alert = session.scalar(
        select(InventoryAlertEvent).where(
            InventoryAlertEvent.tenant_id == tenant.id,
            InventoryAlertEvent.alert_type == "LOW_STOCK",
        )
    )
    assert alert is not None
    assert alert.email_notification_status == "queued"


def test_inventory_outbox_idempotent_reprocess(
    session: Session, tenant: Tenant
) -> None:
    _seed(session, tenant)
    worker = InventoryOutboxWorker(
        get_session_factory(),
        settings=Settings(outbox_batch_size=10, outbox_max_retries=3),
    )
    worker.process_batch()
    session.expire_all()
    notifs_1 = list(
        session.scalars(
            select(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant.id)
        ).all()
    )
    assert len(notifs_1) >= 1

    # Re-queue a processed row as pending to simulate crash-before-mark.
    alert_row = session.scalar(
        select(InventoryOutboxEvent).where(
            InventoryOutboxEvent.tenant_id == tenant.id,
            InventoryOutboxEvent.event_type == "INVENTORY_LOW_STOCK",
        )
    )
    assert alert_row is not None
    alert_row.status = STATUS_PENDING
    alert_row.processed_at = None
    alert_row.next_attempt_at = None
    session.commit()

    worker.process_batch()
    session.expire_all()
    notifs_2 = list(
        session.scalars(
            select(NotificationOutbox).where(NotificationOutbox.tenant_id == tenant.id)
        ).all()
    )
    # Notification enqueue uses alert_event idempotency key — no duplicate.
    assert len(notifs_2) == len(notifs_1)


def test_inventory_outbox_retry_then_dead_letter(
    session: Session, tenant: Tenant
) -> None:
    _seed(session, tenant)
    row = session.scalar(
        select(InventoryOutboxEvent).where(
            InventoryOutboxEvent.tenant_id == tenant.id,
            InventoryOutboxEvent.event_type == "INVENTORY_LOW_STOCK",
        )
    )
    assert row is not None
    # Corrupt payload so handler fails closed into retry path.
    row.payload = {"alert_event_id": "not-a-uuid"}
    session.commit()

    settings = Settings(
        outbox_batch_size=5,
        outbox_max_retries=2,
        outbox_base_backoff_seconds=0.1,
        outbox_max_backoff_seconds=1.0,
    )
    worker = InventoryOutboxWorker(get_session_factory(), settings=settings)
    worker.process_batch()
    session.expire_all()
    session.refresh(row)
    assert row.status == STATUS_PENDING
    assert row.attempt_count == 1
    assert row.error

    row.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
    session.commit()
    worker.process_batch()
    session.refresh(row)
    assert row.status == STATUS_DEAD
    assert row.attempt_count == 2


def test_inventory_outbox_processed_not_reclaimed(
    session: Session, tenant: Tenant
) -> None:
    _seed(session, tenant)
    worker = InventoryOutboxWorker(
        get_session_factory(),
        settings=Settings(outbox_batch_size=10, outbox_max_retries=3),
    )
    worker.process_batch()
    n2 = worker.process_batch()
    assert n2 == 0
    processed = list(
        session.scalars(
            select(InventoryOutboxEvent).where(
                InventoryOutboxEvent.tenant_id == tenant.id,
                InventoryOutboxEvent.status == STATUS_PROCESSED,
            )
        ).all()
    )
    assert processed
