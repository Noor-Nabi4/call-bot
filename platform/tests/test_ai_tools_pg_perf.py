"""PostgreSQL performance / EXPLAIN / N+1 checks for Phase 14 AI tools.

Seeds a realistic local dataset and records measured latencies +
EXPLAIN (ANALYZE, BUFFERS). Skip when Postgres is unavailable.
"""

from __future__ import annotations

import json
import os
import time
import uuid
from datetime import UTC, datetime, timedelta

import pytest
from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.ai_tools import AIToolExecutor
from callbot_platform.crm.appointments.hours import BusinessHoursService
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.inventory import InventoryService
from callbot_platform.crm.products import ProductCatalogService
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Base, Tenant
from callbot_platform.jobs.repos import TechnicianRepository
from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

HMAC = "test-metadata-hmac-secret-ai-tools-perf"

PG_URL = os.environ.get(
    "AI_TOOLS_PG_TEST_URL",
    os.environ.get(
        "APPOINTMENTS_PG_TEST_URL",
        "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
    ),
)

_CUSTOMERS = int(os.environ.get("AI_TOOLS_PERF_CUSTOMERS", "10000"))
_PRODUCTS = int(os.environ.get("AI_TOOLS_PERF_PRODUCTS", "1000"))
_APPOINTMENTS = int(os.environ.get("AI_TOOLS_PERF_APPOINTMENTS", "2000"))
_JOBS = int(os.environ.get("AI_TOOLS_PERF_JOBS", "2000"))


def _pg_available(url: str) -> bool:
    try:
        engine = create_engine(url, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _pg_available(PG_URL),
    reason="PostgreSQL not available for AI tools performance tests",
)


@pytest.fixture(scope="module")
def perf_db():
    engine = create_engine(PG_URL, future=True, pool_size=8, max_overflow=4)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS pgcrypto"))
    Base.metadata.create_all(bind=engine)
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                ALTER TABLE appointments
                ADD CONSTRAINT excl_appointments_technician_active_range
                EXCLUDE USING gist (
                    tenant_id WITH =,
                    assigned_technician_id WITH =,
                    tstzrange(starts_at, ends_at, '[)') WITH &&
                )
                WHERE (
                    assigned_technician_id IS NOT NULL
                    AND archived_at IS NULL
                    AND status IN ('TENTATIVE', 'SCHEDULED', 'CONFIRMED', 'IN_PROGRESS')
                )
                """
            )
        )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    session = factory()
    try:
        ctx = _seed(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()

    yield factory, ctx

    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def _seed(session: Session) -> dict:
    tenants: list[uuid.UUID] = []
    for i in range(4):
        t = Tenant(name=f"Perf Tenant {i}", slug=f"perf-{i}-{uuid.uuid4().hex[:6]}")
        session.add(t)
        session.flush()
        ensure_system_roles_for_tenant(session, t.id)
        tenants.append(t.id)

    primary = tenants[0]
    BusinessHoursService(session).update(
        primary,
        actor="perf",
        weekly_hours={
            d: [["00:00", "23:59"]]
            for d in ["mon", "tue", "wed", "thu", "fri", "sat", "sun"]
        },
    )
    service = ServicesPricebookService(session).create_service(
        primary,
        name="Perf Repair",
        actor="perf",
        duration_minutes=60,
        base_price="99.00",
    )
    tech = TechnicianRepository(session).create(
        primary,
        email=f"perf-tech-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Perf Tech",
    )
    session.flush()

    session.execute(
        text(
            """
            INSERT INTO customers (
                id, tenant_id, name, first_name, last_name, status,
                sms_allowed, email_allowed,
                marketing_sms_allowed, marketing_email_allowed,
                created_by, updated_by, created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                CAST(:tenant AS uuid),
                'Customer ' || g,
                'Cust',
                g::text,
                'ACTIVE',
                TRUE,
                TRUE,
                TRUE,
                TRUE,
                'perf',
                'perf',
                NOW(),
                NOW()
            FROM generate_series(1, :n) AS g
            """
        ),
        {"tenant": str(primary), "n": _CUSTOMERS},
    )
    session.execute(
        text(
            """
            INSERT INTO customer_phones (id, tenant_id, customer_id, e164, created_at)
            SELECT
                gen_random_uuid(),
                c.tenant_id,
                c.id,
                '+1555' || lpad((row_number() OVER ())::text, 7, '0'),
                NOW()
            FROM customers c
            WHERE c.tenant_id = CAST(:tenant AS uuid)
            """
        ),
        {"tenant": str(primary)},
    )

    catalog = ProductCatalogService(session)
    inv = InventoryService(session)
    loc = inv.locations.create(
        primary, name="Main", code="MAIN", actor="perf", is_default=True
    )
    loc_id = uuid.UUID(loc["id"])
    sample_variant: uuid.UUID | None = None
    sample_phone = session.execute(
        text(
            """
            SELECT e164 FROM customer_phones
            WHERE tenant_id = CAST(:tenant AS uuid)
            ORDER BY e164 LIMIT 1
            """
        ),
        {"tenant": str(primary)},
    ).scalar_one()

    for i in range(_PRODUCTS):
        prod = catalog.create(
            primary,
            name=f"Product {i}",
            sku=f"SKU-{i:06d}",
            price="19.99",
            actor="perf",
        )
        variant = catalog.variants.create(
            primary,
            uuid.UUID(prod["id"]),
            sku=f"SKU-{i:06d}-A",
            actor="perf",
        )
        item = inv.items.ensure_for_variant(
            primary, uuid.UUID(variant["id"]), actor="perf"
        )
        if i % 25 == 0:
            inv.mutations.purchase(
                primary,
                item.id,
                location_id=loc_id,
                quantity=100,
                actor="perf",
            )
        if sample_variant is None:
            sample_variant = uuid.UUID(variant["id"])
        if i % 100 == 0:
            session.flush()

    session.execute(
        text(
            """
            INSERT INTO jobs (
                id, tenant_id, job_number, customer_id, status, priority,
                service_type, description, checklist, reference_code,
                created_by, updated_by, created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                CAST(:tenant AS uuid),
                'JOB-' || lpad(g::text, 6, '0'),
                c.id,
                'NEW',
                'MEDIUM',
                'Repair',
                'Perf job',
                CAST('[]' AS jsonb),
                'REF-' || lpad(g::text, 6, '0'),
                'perf',
                'perf',
                NOW(),
                NOW()
            FROM generate_series(1, :n) AS g
            JOIN LATERAL (
                SELECT id FROM customers
                WHERE tenant_id = CAST(:tenant AS uuid)
                ORDER BY created_at
                OFFSET ((g - 1) % :n_cust)
                LIMIT 1
            ) c ON TRUE
            """
        ),
        {"tenant": str(primary), "n": _JOBS, "n_cust": _CUSTOMERS},
    )
    session.execute(
        text(
            """
            INSERT INTO job_number_counters (tenant_id, last_value, updated_at)
            VALUES (CAST(:tenant AS uuid), :n, NOW())
            ON CONFLICT (tenant_id) DO UPDATE
            SET last_value = EXCLUDED.last_value, updated_at = NOW()
            """
        ),
        {"tenant": str(primary), "n": _JOBS},
    )

    starts = datetime.now(UTC) + timedelta(days=30)
    # Non-overlapping slots on one technician (60-minute stride).
    session.execute(
        text(
            """
            INSERT INTO appointments (
                id, tenant_id, appointment_number, confirmation_code,
                customer_id, service_id, assigned_technician_id,
                starts_at, ends_at, duration_minutes, timezone, status, priority,
                is_emergency, service_type, created_by, updated_by, created_at, updated_at
            )
            SELECT
                gen_random_uuid(),
                CAST(:tenant AS uuid),
                'APT-' || lpad(g::text, 6, '0'),
                'CNF-' || lpad(g::text, 6, '0'),
                c.id,
                CAST(:service AS uuid),
                CAST(:tech AS uuid),
                CAST(:starts AS timestamptz) + ((g - 1) * 60 || ' minutes')::interval,
                CAST(:starts AS timestamptz) + ((g - 1) * 60 + 30 || ' minutes')::interval,
                30,
                'UTC',
                'SCHEDULED',
                'NORMAL',
                FALSE,
                'Repair',
                'perf',
                'perf',
                NOW(),
                NOW()
            FROM generate_series(1, :n) AS g
            JOIN LATERAL (
                SELECT id FROM customers
                WHERE tenant_id = CAST(:tenant AS uuid)
                ORDER BY created_at
                OFFSET ((g - 1) % :n_cust)
                LIMIT 1
            ) c ON TRUE
            """
        ),
        {
            "tenant": str(primary),
            "service": service["id"],
            "tech": str(tech["id"]),
            "starts": starts.isoformat(),
            "n": _APPOINTMENTS,
            "n_cust": _CUSTOMERS,
        },
    )
    session.execute(
        text(
            """
            INSERT INTO appointment_number_counters (tenant_id, last_value, updated_at)
            VALUES (CAST(:tenant AS uuid), :n, NOW())
            ON CONFLICT (tenant_id) DO UPDATE
            SET last_value = EXCLUDED.last_value, updated_at = NOW()
            """
        ),
        {"tenant": str(primary), "n": _APPOINTMENTS},
    )
    session.execute(
        text(
            """
            INSERT INTO order_number_counters (tenant_id, last_value, updated_at)
            VALUES (CAST(:tenant AS uuid), 0, NOW())
            ON CONFLICT (tenant_id) DO NOTHING
            """
        ),
        {"tenant": str(primary)},
    )
    session.flush()
    return {
        "tenant_id": primary,
        "service_id": uuid.UUID(service["id"]),
        "technician_id": uuid.UUID(tech["id"]),
        "variant_id": sample_variant,
        "sample_phone": sample_phone,
        "customers": _CUSTOMERS,
        "products": _PRODUCTS,
        "appointments": _APPOINTMENTS,
        "jobs": _JOBS,
    }


def _percentile(samples: list[float], p: float) -> float:
    if not samples:
        return 0.0
    ordered = sorted(samples)
    idx = min(len(ordered) - 1, max(0, round((p / 100.0) * (len(ordered) - 1))))
    return ordered[idx]


def _measure(fn, *, repeats: int = 11) -> tuple[float, float]:
    samples: list[float] = []
    for _ in range(repeats):
        t0 = time.perf_counter()
        fn()
        samples.append((time.perf_counter() - t0) * 1000.0)
    return _percentile(samples, 50), _percentile(samples, 95)


def test_ai_tools_latency_and_explain(perf_db) -> None:
    factory, ctx = perf_db
    session = factory()
    try:
        tenant_id = ctx["tenant_id"]
        ex = AIToolExecutor(session, hmac_secret=HMAC)
        customer = CustomerService(session).lookup_by_phone(
            tenant_id, ctx["sample_phone"]
        )
        assert customer is not None
        customer_id = customer["id"]

        def run_find() -> None:
            assert (
                ex.execute(
                    "find_customer",
                    tenant_id=tenant_id,
                    call_id=None,
                    args={"phone": ctx["sample_phone"]},
                )["ok"]
                is True
            )

        def run_context() -> None:
            assert (
                ex.execute(
                    "get_customer_context",
                    tenant_id=tenant_id,
                    call_id=None,
                    args={"customerId": customer_id},
                )["ok"]
                is True
            )

        def run_services() -> None:
            assert (
                ex.execute(
                    "search_services",
                    tenant_id=tenant_id,
                    call_id=None,
                    args={"query": "Perf", "limit": 5},
                )["ok"]
                is True
            )

        def run_availability() -> None:
            day = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
            r = ex.execute(
                "check_availability",
                tenant_id=tenant_id,
                call_id=None,
                args={
                    "serviceId": str(ctx["service_id"]),
                    "technicianId": str(ctx["technician_id"]),
                    "preferredDate": day,
                    "limit": 5,
                },
            )
            assert r["ok"] is True or (r.get("error") or {}).get("code") in {
                "availability_empty",
                "system_unavailable",
            }

        def run_products() -> None:
            assert (
                ex.execute(
                    "search_products",
                    tenant_id=tenant_id,
                    call_id=None,
                    args={"query": "Product", "limit": 5},
                )["ok"]
                is True
            )

        def run_inventory() -> None:
            assert (
                ex.execute(
                    "check_inventory",
                    tenant_id=tenant_id,
                    call_id=None,
                    args={"variantId": str(ctx["variant_id"])},
                )["ok"]
                is True
            )

        def run_price() -> None:
            assert (
                ex.execute(
                    "get_product_price",
                    tenant_id=tenant_id,
                    call_id=None,
                    args={"variantId": str(ctx["variant_id"])},
                )["ok"]
                is True
            )

        def run_orders() -> None:
            assert (
                ex.execute(
                    "find_orders",
                    tenant_id=tenant_id,
                    call_id=None,
                    customer_id=uuid.UUID(customer_id),
                    args={},
                )["ok"]
                is True
            )

        ops = {
            name: _measure(fn)
            for name, fn in {
                "find_customer": run_find,
                "customer_context": run_context,
                "service_search": run_services,
                "availability": run_availability,
                "product_search": run_products,
                "inventory": run_inventory,
                "price": run_price,
                "order_lookup": run_orders,
            }.items()
        }

        # Mutation latencies (fewer repeats — each creates durable rows).
        def _mutate(tool: str, args: dict) -> None:
            op = uuid.uuid4()
            prep = ex.execute(
                tool,
                tenant_id=tenant_id,
                call_id=None,
                args=args,
                confirmed=False,
                operation_id=op,
            )
            assert prep.get("confirmationToken")
            result = ex.execute(
                tool,
                tenant_id=tenant_id,
                call_id=None,
                args=args,
                confirmed=True,
                confirmation_token=prep["confirmationToken"],
                operation_id=op,
            )
            assert result["ok"] is True, result
            session.commit()

        def run_create_customer() -> None:
            phone = f"+1566{uuid.uuid4().int % 10_000_000:07d}"
            _mutate(
                "create_customer",
                {"firstName": "Perf", "phone": phone},
            )

        def run_create_booking() -> None:
            starts = datetime.now(UTC) + timedelta(
                days=120, minutes=uuid.uuid4().int % 10_000
            )
            ends = starts + timedelta(minutes=30)
            _mutate(
                "create_booking",
                {
                    "customerId": customer_id,
                    "serviceId": str(ctx["service_id"]),
                    "technicianId": str(ctx["technician_id"]),
                    "startsAt": starts.isoformat(),
                    "endsAt": ends.isoformat(),
                    "timezone": "UTC",
                    "description": "Perf booking",
                },
            )

        def run_create_order() -> None:
            _mutate(
                "create_order",
                {
                    "customerId": customer_id,
                    "items": [{"variantId": str(ctx["variant_id"]), "quantity": 1}],
                },
            )

        ops["create_customer"] = _measure(run_create_customer, repeats=5)
        ops["booking"] = _measure(run_create_booking, repeats=5)
        ops["order_creation"] = _measure(run_create_order, repeats=5)

        explains = []
        for label, sql, params in [
            (
                "customer phone lookup",
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT c.id FROM customers c
                JOIN customer_phones p ON p.customer_id = c.id
                WHERE p.tenant_id = CAST(:tenant AS uuid) AND p.e164 = :phone
                LIMIT 1
                """,
                {"tenant": str(tenant_id), "phone": ctx["sample_phone"]},
            ),
            (
                "AI idempotency lookup",
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM telephony_idempotency_keys
                WHERE tenant_id = CAST(:tenant AS uuid)
                  AND operation = :op AND key = :key
                LIMIT 1
                """,
                {
                    "tenant": str(tenant_id),
                    "op": "ai_tool:create_customer",
                    "key": str(uuid.uuid4()),
                },
            ),
            (
                "product search",
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM products
                WHERE tenant_id = CAST(:tenant AS uuid)
                  AND archived_at IS NULL AND name ILIKE :q
                LIMIT 5
                """,
                {"tenant": str(tenant_id), "q": "%Product%"},
            ),
            (
                "availability conflict query",
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM appointments
                WHERE tenant_id = CAST(:tenant AS uuid)
                  AND assigned_technician_id = CAST(:tech AS uuid)
                  AND archived_at IS NULL
                  AND status IN ('TENTATIVE','SCHEDULED','CONFIRMED','IN_PROGRESS')
                  AND starts_at < NOW() + interval '2 days'
                  AND ends_at > NOW()
                LIMIT 20
                """,
                {"tenant": str(tenant_id), "tech": str(ctx["technician_id"])},
            ),
            (
                "order lookup",
                """
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM orders
                WHERE tenant_id = CAST(:tenant AS uuid)
                  AND customer_id = CAST(:customer AS uuid)
                ORDER BY created_at DESC
                LIMIT 5
                """,
                {"tenant": str(tenant_id), "customer": customer_id},
            ),
        ]:
            rows = session.execute(text(sql), params).fetchall()
            plan = "\n".join(r[0] for r in rows)
            planning = next(
                (ln for ln in plan.splitlines() if "Planning Time" in ln), ""
            )
            execution = next(
                (ln for ln in plan.splitlines() if "Execution Time" in ln), ""
            )
            explains.append(
                {
                    "query": label,
                    "index_used": any(
                        x in plan for x in ("Index Scan", "Bitmap Index", "Index Only")
                    ),
                    "seq_scan": "Seq Scan" in plan,
                    "planning": planning.strip(),
                    "execution": execution.strip(),
                    "plan_head": "\n".join(plan.splitlines()[:14]),
                }
            )

        queries: list[str] = []

        def _before_cursor(conn, cursor, statement, parameters, context, executemany):
            queries.append(statement)

        bind = session.get_bind()
        event.listen(bind, "before_cursor_execute", _before_cursor)
        try:
            queries.clear()
            ex.execute(
                "get_customer_context",
                tenant_id=tenant_id,
                call_id=None,
                args={"customerId": customer_id},
            )
            context_q = len(queries)
            queries.clear()
            ex.execute(
                "search_products",
                tenant_id=tenant_id,
                call_id=None,
                args={"query": "Product", "limit": 5},
            )
            products_q = len(queries)
            queries.clear()
            ex.execute(
                "find_orders",
                tenant_id=tenant_id,
                call_id=None,
                customer_id=uuid.UUID(customer_id),
                args={},
            )
            orders_q = len(queries)
            queries.clear()
            day = (datetime.now(UTC) + timedelta(days=1)).date().isoformat()
            ex.execute(
                "check_availability",
                tenant_id=tenant_id,
                call_id=None,
                args={
                    "serviceId": str(ctx["service_id"]),
                    "technicianId": str(ctx["technician_id"]),
                    "preferredDate": day,
                    "limit": 5,
                },
            )
            availability_q = len(queries)
        finally:
            event.remove(bind, "before_cursor_execute", _before_cursor)

        assert context_q <= 40, context_q
        assert products_q <= 25, products_q
        assert orders_q <= 20, orders_q
        assert availability_q <= 40, availability_q

        report = {
            "dataset": {
                "tenants": 4,
                "customers": ctx["customers"],
                "products": ctx["products"],
                "variants": ctx["products"],
                "appointments": ctx["appointments"],
                "jobs": ctx["jobs"],
            },
            "latency_ms": {
                k: {"p50": round(v[0], 2), "p95": round(v[1], 2)}
                for k, v in ops.items()
            },
            "n_plus_one": {
                "get_customer_context": context_q,
                "search_products": products_q,
                "find_orders": orders_q,
                "check_availability": availability_q,
            },
            "explains": explains,
        }
        out_path = os.environ.get(
            "AI_TOOLS_PERF_REPORT", "/tmp/ai_tools_pg_perf_report.json"
        )
        with open(out_path, "w", encoding="utf-8") as fh:
            json.dump(report, fh, indent=2)
        print("AI_TOOLS_PERF_REPORT=" + out_path)
        print(json.dumps(report["latency_ms"], indent=2))
        print(json.dumps(report["n_plus_one"], indent=2))
    finally:
        session.close()
