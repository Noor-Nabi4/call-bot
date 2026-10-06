"""Local micro-benchmark for Customer CRM hot paths (not staging-scale)."""

from __future__ import annotations

import time
import uuid

from callbot_platform.crm.customers import CustomerService
from callbot_platform.db import get_session_factory, init_db
from callbot_platform.db.models import Tenant


def _bench(label: str, fn, *, rounds: int = 20) -> float:
    # Warmup
    fn()
    start = time.perf_counter()
    for _ in range(rounds):
        fn()
    elapsed = (time.perf_counter() - start) / rounds * 1000
    print(f"{label}: {elapsed:.3f} ms/op (n={rounds})")
    return elapsed


def main() -> None:
    init_db("sqlite:///:memory:")
    session = get_session_factory()()
    tenant = Tenant(name="Bench", slug=f"bench-{uuid.uuid4().hex[:8]}")
    session.add(tenant)
    session.flush()
    svc = CustomerService(session)

    ids: list[uuid.UUID] = []
    for i in range(200):
        row = svc.create(
            tenant.id,
            name=f"Customer {i:04d}",
            phone=f"+1555100{i:04d}",
            email=f"user{i:04d}@example.com",
        )
        cid = uuid.UUID(row["id"])
        ids.append(cid)
        if i % 3 == 0:
            svc.locations.create_location(
                tenant.id,
                cid,
                address_line_1=f"{i} Main Street",
                city="Austin",
                postal_code="78701",
            )

    target = ids[42]
    _bench("exact_phone", lambda: svc.search(tenant.id, q="+15551000042"))
    _bench("exact_email", lambda: svc.search(tenant.id, q="user0042@example.com"))
    _bench("name_prefix", lambda: svc.search(tenant.id, q="Customer 00"))
    _bench("address", lambda: svc.search(tenant.id, q="Main Street"))
    _bench("list_page", lambda: svc.list(tenant.id, limit=50))
    _bench("get", lambda: svc.get(tenant.id, target))
    _bench(
        "timeline_empty",
        lambda: svc.timeline(
            tenant.id,
            target,
            allowed_permission_keys=frozenset({"customers.read", "calls.read"}),
        ),
    )
    print("NOTE: sqlite in-memory microbench only — Staging EXPLAIN: NOT EXECUTED")


if __name__ == "__main__":
    main()
