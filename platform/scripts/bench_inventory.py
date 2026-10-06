"""Local micro-benchmark for inventory hot paths (not staging-scale)."""

from __future__ import annotations

import time
import uuid

from callbot_platform.crm.inventory import InventoryService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.db import get_session_factory, init_db
from callbot_platform.db.models import Tenant


def _bench(label: str, fn, *, rounds: int = 20) -> None:
    fn()
    start = time.perf_counter()
    for _ in range(rounds):
        fn()
    print(f"{label}: {(time.perf_counter() - start) / rounds * 1000:.3f} ms/op (n={rounds})")


def main() -> None:
    init_db("sqlite:///:memory:")
    session = get_session_factory()()
    tenant = Tenant(name="Bench", slug=f"bench-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    catalog = ProductCatalogService(session)
    inv = InventoryService(session)
    loc = inv.locations.create(
        tenant.id, name="Main", code="MAIN", actor="bench", is_default=True
    )
    loc_id = uuid.UUID(loc["id"])
    for i in range(200):
        prod = catalog.create(
            tenant.id,
            name=f"Item {i:04d}",
            sku=f"SKU-{i:04d}",
            price="10",
            actor="bench",
        )
        variant = catalog.variants.create(
            tenant.id, uuid.UUID(prod["id"]), sku=f"SKU-{i:04d}-A", actor="bench"
        )
        item = inv.items.ensure_for_variant(
            tenant.id, uuid.UUID(variant["id"]), actor="bench"
        )
        inv.mutations.purchase(
            tenant.id,
            item.id,
            location_id=loc_id,
            quantity=10 + (i % 5),
            actor="bench",
        )
    session.commit()
    sample = inv.get_inventory_by_sku(tenant.id, variant["sku"])
    sample_item_id = uuid.UUID(sample["id"])
    _bench("list_inventory", lambda: inv.list_inventory(tenant.id, limit=50))
    _bench("dashboard", lambda: inv.dashboard(tenant.id))
    _bench("low_stock_filter", lambda: inv.list_inventory(tenant.id, low_stock_only=True))
    _bench(
        "transaction_history",
        lambda: inv.list_transactions(tenant.id, sample_item_id, limit=50),
    )
    _bench(
        "sku_lookup",
        lambda: inv.get_inventory_by_sku(tenant.id, variant["sku"]),
    )
    print("NOTE: LOCAL SQLITE ONLY — Staging EXPLAIN: NOT EXECUTED")


if __name__ == "__main__":
    main()
