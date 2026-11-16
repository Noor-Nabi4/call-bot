"""PostgreSQL concurrency tests for Phase 10 Jobs.

Skip when Postgres is unavailable — SQLite cannot prove FOR UPDATE races.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs import JobService
from callbot_platform.crm.services.service import ServicesPricebookService
from callbot_platform.db.models import Base, Tenant
from callbot_platform.db.models.jobs import Job, JobNumberCounter, JobStatusHistory
from callbot_platform.jobs.repos import TechnicianRepository

PG_URL = os.environ.get(
    "JOBS_PG_TEST_URL",
    os.environ.get(
        "ORDERS_PG_TEST_URL",
        os.environ.get(
            "LEADS_PG_TEST_URL",
            os.environ.get(
                "INVENTORY_PG_TEST_URL",
                "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
            ),
        ),
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


pytestmark = pytest.mark.skipif(
    not _pg_available(PG_URL),
    reason="PostgreSQL not available for jobs concurrency tests",
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
    row = Tenant(name="Jobs PG", slug=f"jobs-pg-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _field_service(session: Session, tenant_id: uuid.UUID) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Buyer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="setup",
    )
    service = ServicesPricebookService(session).create_service(
        tenant_id, name="Repair", actor="setup"
    )
    tech = TechnicianRepository(session).create(
        tenant_id,
        email=f"tech-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Field Tech",
    )
    return {
        "customer_id": uuid.UUID(customer["id"]),
        "service_id": uuid.UUID(service["id"]),
        "technician_id": uuid.UUID(tech["id"]),
    }


def test_concurrent_job_number_generation(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_service(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
    finally:
        session.close()

    def worker(n: int) -> str:
        s = pg_factory()
        try:
            job = JobService(s).create(
                tenant_id,
                customer_id=setup_ids["customer_id"],
                actor=f"w-{n}",
                service_id=setup_ids["service_id"],
            )
            s.commit()
            return job["job_number"]
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        numbers = list(pool.map(worker, range(8)))
    assert len(numbers) == len(set(numbers))
    assert all(n.startswith("JOB-") for n in numbers)


def test_concurrent_status_transition_serialized(pg_factory) -> None:
    """IN_PROGRESS→COMPLETED vs IN_PROGRESS→CANCELLED are mutually exclusive."""
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_service(session, tenant.id)
        job = JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            service_id=setup["service_id"],
            status="SCHEDULED",
        )
        jid = uuid.UUID(job["id"])
        api = JobService(session)
        api.assign(tenant.id, jid, technician_id=setup["technician_id"], actor="setup")
        api.transition(tenant.id, jid, to_status="DISPATCHED", actor="setup")
        api.transition(tenant.id, jid, to_status="IN_PROGRESS", actor="setup")
        session.commit()
        tenant_id = tenant.id
        job_id = jid
    finally:
        session.close()

    def worker(to_status: str, *, completion_notes: str | None = None) -> dict:
        s = pg_factory()
        try:
            kwargs: dict = {}
            if completion_notes is not None:
                kwargs["completion_notes"] = completion_notes
            result = JobService(s).transition(
                tenant_id, job_id, to_status=to_status, actor=f"w-{to_status}", **kwargs
            )
            s.commit()
            return {"ok": True, "status": result["status"]}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, "COMPLETED", completion_notes="Done"),
            pool.submit(worker, "CANCELLED"),
        ]
        results = [f.result() for f in as_completed(futures)]

    oks = [r for r in results if r["ok"]]
    fails = [r for r in results if not r["ok"]]
    assert len(oks) == 1
    assert len(fails) == 1
    assert fails[0]["code"] == "invalid_transition"

    s = pg_factory()
    try:
        final = s.scalar(select(Job).where(Job.id == job_id))
        assert final is not None
        assert final.status in {"COMPLETED", "CANCELLED"}
        hist = s.scalar(
            select(func.count())
            .select_from(JobStatusHistory)
            .where(
                JobStatusHistory.job_id == job_id,
                JobStatusHistory.from_status == "IN_PROGRESS",
            )
        )
        assert hist == 1
    finally:
        s.close()


def test_concurrent_assign_race_single_winner_consistency(pg_factory) -> None:
    """Two technicians racing to self-assign — DB stays consistent either way."""
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_service(session, tenant.id)
        tech2 = TechnicianRepository(session).create(
            tenant.id,
            email=f"tech2-{uuid.uuid4().hex[:6]}@t.test",
            password="password123",
            name="Field Tech Two",
        )
        job = JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            service_id=setup["service_id"],
        )
        session.commit()
        tenant_id = tenant.id
        job_id = uuid.UUID(job["id"])
        tech_a = setup["technician_id"]
        tech_b = uuid.UUID(tech2["id"])
    finally:
        session.close()

    def worker(tech_id: uuid.UUID) -> dict:
        s = pg_factory()
        try:
            result = JobService(s).assign(
                tenant_id, job_id, technician_id=tech_id, actor="w"
            )
            s.commit()
            return {"ok": True, "technician_id": result["assigned_technician_id"]}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, tech_a), pool.submit(worker, tech_b)]
        results = [f.result() for f in as_completed(futures)]

    assert all(r["ok"] for r in results)

    s = pg_factory()
    try:
        final = s.scalar(select(Job).where(Job.id == job_id))
        assert final is not None
        assert final.assigned_technician_id in {tech_a, tech_b}
    finally:
        s.close()


def test_duplicate_idempotency_key_create(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_service(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
    finally:
        session.close()

    def worker(n: int) -> str:
        s = pg_factory()
        try:
            job = JobService(s).create(
                tenant_id,
                customer_id=setup_ids["customer_id"],
                actor=f"w-{n}",
                service_id=setup_ids["service_id"],
                idempotency_key="same-key",
            )
            s.commit()
            return job["id"]
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=6) as pool:
        ids = list(pool.map(worker, range(6)))
    assert len(set(ids)) == 1

    s = pg_factory()
    try:
        count = s.scalar(
            select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id)
        )
        assert count == 1
    finally:
        s.close()


def test_duplicate_transition_idempotent(pg_factory) -> None:
    """Repeating the same no-op transition concurrently must not duplicate history."""
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_service(session, tenant.id)
        job = JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            service_id=setup["service_id"],
            status="SCHEDULED",
        )
        jid = uuid.UUID(job["id"])
        JobService(session).assign(
            tenant.id, jid, technician_id=setup["technician_id"], actor="setup"
        )
        JobService(session).transition(
            tenant.id, jid, to_status="DISPATCHED", actor="setup"
        )
        session.commit()
        tenant_id = tenant.id
        job_id = jid
    finally:
        session.close()

    def worker(n: int) -> dict:
        s = pg_factory()
        try:
            result = JobService(s).transition(
                tenant_id, job_id, to_status="DISPATCHED", actor=f"w-{n}"
            )
            s.commit()
            return {"ok": True, "status": result["status"]}
        except Exception as exc:
            s.rollback()
            return {"ok": False, "err": str(exc)}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=4) as pool:
        results = list(pool.map(worker, range(4)))
    assert all(r["ok"] for r in results)

    s = pg_factory()
    try:
        hist = s.scalar(
            select(func.count())
            .select_from(JobStatusHistory)
            .where(
                JobStatusHistory.job_id == job_id,
                JobStatusHistory.from_status == "SCHEDULED",
                JobStatusHistory.to_status == "DISPATCHED",
            )
        )
        # Same-status transition is a no-op (returns current state); only the
        # original SCHEDULED→DISPATCHED transition is recorded once.
        assert hist == 1
    finally:
        s.close()


def test_concurrent_no_show_vs_cancel(pg_factory) -> None:
    """NO_SHOW vs CANCELLED from SCHEDULED — exactly one terminal wins."""
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_service(session, tenant.id)
        job = JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            service_id=setup["service_id"],
            status="SCHEDULED",
        )
        session.commit()
        tenant_id = tenant.id
        job_id = uuid.UUID(job["id"])
    finally:
        session.close()

    def worker(to_status: str) -> dict:
        s = pg_factory()
        try:
            result = JobService(s).transition(
                tenant_id, job_id, to_status=to_status, actor=f"w-{to_status}"
            )
            s.commit()
            return {"ok": True, "status": result["status"]}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, "NO_SHOW"),
            pool.submit(worker, "CANCELLED"),
        ]
        results = [f.result() for f in as_completed(futures)]

    oks = [r for r in results if r["ok"]]
    fails = [r for r in results if not r["ok"]]
    assert len(oks) == 1
    assert len(fails) == 1
    assert fails[0]["code"] == "invalid_transition"

    s = pg_factory()
    try:
        final = s.scalar(select(Job).where(Job.id == job_id))
        assert final is not None
        assert final.status in {"NO_SHOW", "CANCELLED"}
        hist = s.scalar(
            select(func.count())
            .select_from(JobStatusHistory)
            .where(
                JobStatusHistory.job_id == job_id,
                JobStatusHistory.from_status == "SCHEDULED",
            )
        )
        assert hist == 1
    finally:
        s.close()


def test_idempotency_fingerprint_conflict_pg(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_service(session, tenant.id)
        JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="t",
            service_type="Install",
            idempotency_key="fp-conflict",
        )
        session.commit()
        tenant_id = tenant.id
        customer_id = setup["customer_id"]
    finally:
        session.close()

    s = pg_factory()
    try:
        with pytest.raises(CrmError) as exc:
            JobService(s).create(
                tenant_id,
                customer_id=customer_id,
                actor="t",
                service_type="Repair",
                idempotency_key="fp-conflict",
            )
        assert exc.value.code == "idempotency_conflict"
        count = s.scalar(
            select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id)
        )
        assert count == 1
    finally:
        s.close()


def test_multi_tenant_job_numbers_isolated(pg_factory) -> None:
    session = pg_factory()
    try:
        t1 = _tenant(session)
        t2 = Tenant(name="Jobs PG B", slug=f"jobs-pg-b-{uuid.uuid4().hex[:8]}")
        session.add(t2)
        session.flush()
        s1 = _field_service(session, t1.id)
        s2 = _field_service(session, t2.id)
        session.commit()
        tid1, tid2 = t1.id, t2.id
        setup1, setup2 = s1, s2
    finally:
        session.close()

    def worker(tenant_id: uuid.UUID, setup: dict, n: int) -> str:
        s = pg_factory()
        try:
            job = JobService(s).create(
                tenant_id,
                customer_id=setup["customer_id"],
                actor=f"w-{n}",
                service_id=setup["service_id"],
            )
            s.commit()
            return job["job_number"]
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        f1 = [pool.submit(worker, tid1, setup1, i) for i in range(4)]
        f2 = [pool.submit(worker, tid2, setup2, i) for i in range(4)]
        n1 = [f.result() for f in f1]
        n2 = [f.result() for f in f2]
    assert len(set(n1)) == 4
    assert len(set(n2)) == 4
    assert "JOB-000001" in n1 and "JOB-000001" in n2

    s = pg_factory()
    try:
        counters = s.scalar(select(func.count()).select_from(JobNumberCounter))
        assert counters == 2
    finally:
        s.close()


def test_explain_job_hot_paths(pg_factory) -> None:
    """Capture EXPLAIN ANALYZE for hot Job queries (evidence, not thresholds).

    Seeds a multi-tenant dataset (~8k jobs via bulk SQL) so the planner sees
    non-trivial cardinality. This is local evidence only — not a staging/prod claim.
    """
    session = pg_factory()
    try:
        tenants: list[Tenant] = []
        setups: list[dict] = []
        for _ in range(4):
            t = _tenant(session)
            tenants.append(t)
            setups.append(_field_service(session, t.id))
        session.flush()

        # Bulk insert for planner cardinality without per-row service overhead.
        for ti, setup in enumerate(setups):
            tid = tenants[ti].id
            session.execute(
                text(
                    """
                    INSERT INTO jobs (
                        id, tenant_id, job_number, customer_id, service_id,
                        status, priority, service_type, checklist, reference_code,
                        created_at, updated_at
                    )
                    SELECT
                        gen_random_uuid(),
                        CAST(:tid AS uuid),
                        'JOB-' || lpad(gs::text, 6, '0'),
                        CAST(:cid AS uuid),
                        CAST(:sid AS uuid),
                        'NEW',
                        'MEDIUM',
                        'Bulk Service',
                        '[]'::jsonb,
                        'REF-' || lpad(gs::text, 6, '0'),
                        NOW() - (gs || ' minutes')::interval,
                        NOW()
                    FROM generate_series(1, 2000) AS gs
                    """
                ),
                {
                    "tid": str(tid),
                    "cid": str(setup["customer_id"]),
                    "sid": str(setup["service_id"]),
                },
            )
        session.commit()
        tid = str(tenants[0].id)
        cid = str(setups[0]["customer_id"])
        techid = str(setups[0]["technician_id"])
        sid = str(setups[0]["service_id"])

        plans: dict[str, str] = {}
        queries = {
            "list_cursor": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM jobs
                WHERE tenant_id = '{tid}' AND archived_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT 50
            """,
            "job_number": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM jobs
                WHERE tenant_id = '{tid}' AND job_number = 'JOB-000001'
            """,
            "customer_filter": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM jobs
                WHERE tenant_id = '{tid}' AND customer_id = '{cid}'
                  AND archived_at IS NULL
                ORDER BY created_at DESC
                LIMIT 50
            """,
            "status_filter": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM jobs
                WHERE tenant_id = '{tid}' AND status = 'NEW'
                  AND archived_at IS NULL
                ORDER BY created_at DESC
                LIMIT 50
            """,
            "technician_filter": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM jobs
                WHERE tenant_id = '{tid}' AND assigned_technician_id = '{techid}'
            """,
            "service_filter": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM jobs
                WHERE tenant_id = '{tid}' AND service_id = '{sid}'
                  AND archived_at IS NULL
                ORDER BY created_at DESC
                LIMIT 50
            """,
            "scheduled_start": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM jobs
                WHERE tenant_id = '{tid}'
                  AND scheduled_starts_at IS NOT NULL
                ORDER BY scheduled_starts_at ASC
                LIMIT 50
            """,
            "date_range": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM jobs
                WHERE tenant_id = '{tid}'
                  AND created_at >= NOW() - INTERVAL '7 days'
                ORDER BY created_at DESC
                LIMIT 50
            """,
            "history": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM job_status_history
                WHERE tenant_id = '{tid}'
                ORDER BY created_at ASC
                LIMIT 50
            """,
            "timeline_jobs": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM jobs
                WHERE tenant_id = '{tid}' AND customer_id = '{cid}'
                ORDER BY created_at DESC
                LIMIT 50
            """,
        }
        for name, sql in queries.items():
            rows = session.execute(text(sql)).fetchall()
            plans[name] = "\n".join(r[0] for r in rows)
            assert "Seq Scan" in plans[name] or "Index" in plans[name]
        assert all(plans.values())
        assert "Index" in plans["list_cursor"] or "Seq Scan" in plans["list_cursor"]
        assert "Index" in plans["job_number"] or "Seq Scan" in plans["job_number"]
    finally:
        session.close()


def test_create_atomicity_nested_failure(pg_factory) -> None:
    """If the status-history insert fails, the outer rollback leaves no orphans."""
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _field_service(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
        setup_ids = setup
    finally:
        session.close()

    s = pg_factory()
    try:
        api = JobService(s)
        job = api.create(
            tenant_id,
            customer_id=setup_ids["customer_id"],
            actor="t",
            service_id=setup_ids["service_id"],
        )
        s.rollback()  # discard uncommitted create
        count = s.scalar(
            select(func.count()).select_from(Job).where(Job.tenant_id == tenant_id)
        )
        assert count == 0
        _ = job
    finally:
        s.close()
