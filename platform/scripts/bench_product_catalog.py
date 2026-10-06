"""Local micro-benchmark for Product Catalog hot paths (not staging-scale)."""

from __future__ import annotations

import time
import uuid

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
    svc = ProductCatalogService(session)
    cat = svc.categories.create(tenant.id, name="Root", actor="bench")
    cat_id = uuid.UUID(cat["id"])
    for i in range(200):
        svc.create(
            tenant.id,
            name=f"Product {i:04d}",
            sku=f"SKU-{i:04d}",
            price=str(10 + i % 50),
            category_id=cat_id,
            brand="BenchBrand",
            actor="bench",
        )
    _bench("exact_sku", lambda: svc.search(tenant.id, q="SKU-0042"))
    _bench("name_prefix", lambda: svc.search(tenant.id, q="Product 00"))
    _bench("category_filter", lambda: svc.list(tenant.id, category_id=cat_id, limit=50))
    _bench("list_page", lambda: svc.list(tenant.id, limit=50))
    _bench("category_tree", lambda: svc.categories.tree(tenant.id))
    print("NOTE: sqlite in-memory microbench only — Staging EXPLAIN: NOT EXECUTED")


if __name__ == "__main__":
    main()
