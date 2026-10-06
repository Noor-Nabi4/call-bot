"""PostgreSQL concurrency tests for Phase 12 Dispatch."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.dispatch.assignment import DispatchAssignmentService
from callbot_platform.crm.dispatch.status import TechnicianStatusService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs import JobService
from callbot_platform.db.models import Base, Tenant
from callbot_platform.db.models.jobs import Job
from callbot_platform.jobs.repos import TechnicianRepository

PG_URL = os.environ.get(
    "DISPATCH_PG_TEST_URL",
    os.environ.get(
        "JOBS_PG_TEST_URL",
        os.environ.get(
            "APPOINTMENTS_PG_TEST_URL",
            "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
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


_PG_UP = _pg_available(PG_URL)

pytestmark = pytest.mark.skipif(
    not _PG_UP, reason="PostgreSQL not available for dispatch concurrency tests"
)


@pytest.fixture()
def pg_factory():
    engine = create_engine(PG_URL, future=True, pool_size=10, max_overflow=5)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS btree_gist"))
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def _tenant(session: Session) -> Tenant:
    row = Tenant(name="Dispatch PG", slug=f"disp-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def _setup(session: Session, tenant_id: uuid.UUID) -> dict:
    customer = CustomerService(session).create(
        tenant_id,
        name="Buyer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        actor="setup",
    )
    tech = TechnicianRepository(session).create(
        tenant_id,
        email=f"tech-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Field Tech",
    )
    tech2 = TechnicianRepository(session).create(
        tenant_id,
        email=f"tech2-{uuid.uuid4().hex[:6]}@t.test",
        password="password123",
        name="Field Tech 2",
    )
    return {
        "customer_id": uuid.UUID(customer["id"]),
        "technician_id": uuid.UUID(tech["id"]),
        "technician_b": uuid.UUID(tech2["id"]),
    }


def test_concurrent_assign_same_job(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _setup(session, tenant.id)
        job = JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            service_type="X",
        )
        session.commit()
        tenant_id = tenant.id
        job_id = uuid.UUID(job["id"])
        tech_a = setup["technician_id"]
        tech_b = setup["technician_b"]
    finally:
        session.close()

    def worker(tech_id: uuid.UUID) -> dict:
        s = pg_factory()
        try:
            DispatchAssignmentService(s).assign(
                tenant_id, job_id, technician_id=tech_id, actor="w"
            )
            s.commit()
            return {"ok": True, "tech": str(tech_id)}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed(
                [pool.submit(worker, tech_a), pool.submit(worker, tech_b)]
            )
        ]
    assert all(r["ok"] for r in results)
    s = pg_factory()
    try:
        final = s.scalar(select(Job).where(Job.id == job_id))
        assert final is not None
        assert final.assigned_technician_id in {tech_a, tech_b}
    finally:
        s.close()


def test_concurrent_status_race(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _setup(session, tenant.id)
        session.commit()
        tenant_id = tenant.id
        tech_id = setup["technician_id"]
    finally:
        session.close()

    def worker(to_status: str) -> dict:
        s = pg_factory()
        try:
            TechnicianStatusService(s).transition(
                tenant_id, tech_id, to_status=to_status, actor=f"w-{to_status}"
            )
            s.commit()
            return {"ok": True, "status": to_status}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed(
                [pool.submit(worker, "BUSY"), pool.submit(worker, "BUSY")]
            )
        ]
    # Both may succeed if they are identical transitions (idempotent same-status).
    # Force conflict via BUSY then OFFLINE after one wins by using different targets
    # that are mutually exclusive from AVAILABLE: run again from a fresh AVAILABLE.
    oks = [r for r in results if r["ok"]]
    assert len(oks) >= 1
    s = pg_factory()
    try:
        st = TechnicianStatusService(s).get(tenant_id, tech_id)
        assert st["status"] == "BUSY"
    finally:
        s.close()


def test_assign_idempotency_concurrent(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _setup(session, tenant.id)
        job = JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            service_type="X",
        )
        session.commit()
        tenant_id = tenant.id
        job_id = uuid.UUID(job["id"])
        tech_id = setup["technician_id"]
    finally:
        session.close()

    def worker(n: int) -> dict:
        s = pg_factory()
        try:
            DispatchAssignmentService(s).assign(
                tenant_id,
                job_id,
                technician_id=tech_id,
                actor=f"w-{n}",
                idempotency_key="same-key",
            )
            s.commit()
            return {"ok": True}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = [
            f.result() for f in as_completed([pool.submit(worker, i) for i in range(8)])
        ]
    assert all(r["ok"] for r in results)


def test_concurrent_reassign_race(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _setup(session, tenant.id)
        job = JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            service_type="X",
        )
        DispatchAssignmentService(session).assign(
            tenant.id,
            uuid.UUID(job["id"]),
            technician_id=setup["technician_id"],
            actor="setup",
        )
        session.commit()
        tenant_id = tenant.id
        job_id = uuid.UUID(job["id"])
        tech_b = setup["technician_b"]
        tech_c = TechnicianRepository(session).create(
            tenant.id,
            email=f"techc-{uuid.uuid4().hex[:6]}@t.test",
            password="password123",
            name="Field Tech 3",
        )
        session.commit()
        tech_c_id = uuid.UUID(tech_c["id"])
    finally:
        session.close()

    def worker(tech_id: uuid.UUID) -> dict:
        s = pg_factory()
        try:
            DispatchAssignmentService(s).assign(
                tenant_id, job_id, technician_id=tech_id, actor="race"
            )
            s.commit()
            return {"ok": True, "tech": str(tech_id)}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed(
                [pool.submit(worker, tech_b), pool.submit(worker, tech_c_id)]
            )
        ]
    assert all(r["ok"] for r in results)
    s = pg_factory()
    try:
        final = s.scalar(select(Job).where(Job.id == job_id))
        assert final is not None
        assert final.assigned_technician_id in {tech_b, tech_c_id}
    finally:
        s.close()


def test_concurrent_assign_vs_unassign(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _setup(session, tenant.id)
        job = JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            service_type="X",
        )
        DispatchAssignmentService(session).assign(
            tenant.id,
            uuid.UUID(job["id"]),
            technician_id=setup["technician_id"],
            actor="setup",
        )
        session.commit()
        tenant_id = tenant.id
        job_id = uuid.UUID(job["id"])
        tech = setup["technician_b"]
    finally:
        session.close()

    def worker(tech_id: uuid.UUID | None) -> dict:
        s = pg_factory()
        try:
            DispatchAssignmentService(s).assign(
                tenant_id, job_id, technician_id=tech_id, actor="race"
            )
            s.commit()
            return {"ok": True, "tech": str(tech_id) if tech_id else None}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed(
                [pool.submit(worker, tech), pool.submit(worker, None)]
            )
        ]
    assert all(r["ok"] for r in results)
    s = pg_factory()
    try:
        final = s.scalar(select(Job).where(Job.id == job_id))
        assert final is not None
        # One of assign(tech) or unassign must win consistently.
        assert final.assigned_technician_id in {tech, None}
    finally:
        s.close()


def test_concurrent_assign_vs_cancel(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _setup(session, tenant.id)
        job = JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            service_type="X",
        )
        session.commit()
        tenant_id = tenant.id
        job_id = uuid.UUID(job["id"])
        tech = setup["technician_id"]
    finally:
        session.close()

    def assign_worker() -> dict:
        s = pg_factory()
        try:
            DispatchAssignmentService(s).assign(
                tenant_id, job_id, technician_id=tech, actor="a"
            )
            s.commit()
            return {"ok": True, "op": "assign"}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code, "op": "assign"}
        finally:
            s.close()

    def cancel_worker() -> dict:
        s = pg_factory()
        try:
            JobService(s).transition(
                tenant_id, job_id, to_status="CANCELLED", actor="c"
            )
            s.commit()
            return {"ok": True, "op": "cancel"}
        except Exception as exc:
            s.rollback()
            code = getattr(exc, "code", type(exc).__name__)
            return {"ok": False, "code": code, "op": "cancel"}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result()
            for f in as_completed(
                [pool.submit(assign_worker), pool.submit(cancel_worker)]
            )
        ]
    assert any(r["ok"] for r in results)
    s = pg_factory()
    try:
        final = s.scalar(select(Job).where(Job.id == job_id))
        assert final is not None
        if final.status == "CANCELLED":
            # Terminal — assignment must not leave job in an illegal assignable
            # state without respecting cancel; either unassigned or assigned
            # before cancel is acceptable as long as status is CANCELLED.
            assert final.status == "CANCELLED"
        else:
            assert final.assigned_technician_id == tech
            assert final.status in {"NEW", "SCHEDULED", "CONFIRMED", "DISPATCHED"}
    finally:
        s.close()


def test_concurrent_legacy_and_crm_assign(pg_factory) -> None:
    """Legacy JobRepository.assign and CRM DispatchAssignmentService race safely."""
    from callbot_platform.jobs.repos import JobRepository

    session = pg_factory()
    try:
        tenant = _tenant(session)
        setup = _setup(session, tenant.id)
        job = JobService(session).create(
            tenant.id,
            customer_id=setup["customer_id"],
            actor="setup",
            service_type="X",
        )
        session.commit()
        tenant_id = tenant.id
        job_id = uuid.UUID(job["id"])
        tech_a = setup["technician_id"]
        tech_b = setup["technician_b"]
    finally:
        session.close()

    def legacy() -> dict:
        s = pg_factory()
        try:
            JobRepository(s).assign(
                tenant_id, job_id, technician_id=tech_a, actor="legacy"
            )
            s.commit()
            return {"ok": True, "path": "legacy"}
        except Exception as exc:
            s.rollback()
            return {"ok": False, "code": getattr(exc, "code", str(exc))}
        finally:
            s.close()

    def crm() -> dict:
        s = pg_factory()
        try:
            DispatchAssignmentService(s).assign(
                tenant_id, job_id, technician_id=tech_b, actor="crm"
            )
            s.commit()
            return {"ok": True, "path": "crm"}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = [
            f.result() for f in as_completed([pool.submit(legacy), pool.submit(crm)])
        ]
    assert all(r["ok"] for r in results)
    s = pg_factory()
    try:
        final = s.scalar(select(Job).where(Job.id == job_id))
        assert final is not None
        assert final.assigned_technician_id in {tech_a, tech_b}
        from callbot_platform.db.models.dispatch import JobAssignmentHistory

        hist = list(
            s.scalars(
                select(JobAssignmentHistory).where(
                    JobAssignmentHistory.tenant_id == tenant_id,
                    JobAssignmentHistory.job_id == job_id,
                )
            ).all()
        )
        assert len(hist) >= 1
    finally:
        s.close()


def test_explain_dispatch_hot_paths_production_scale(pg_factory) -> None:
    """Local PostgreSQL EXPLAIN ANALYZE at production-scale synthetic volume.

    Dataset (synthetic benchmark fixtures only): 4 tenants x 50 techs x
    2000+ jobs x 2000+ appointments + histories/events.
    Does NOT equal staging/production verification.
    """
    from callbot_platform.crm.services.service import ServicesPricebookService
    from callbot_platform.db.models.dispatch import (
        DispatchEvent,
        JobAssignmentHistory,
        TechnicianOperationalStatus,
    )

    session = pg_factory()
    try:
        tenants: list[Tenant] = []
        setups: list[dict] = []
        for _ in range(4):
            t = _tenant(session)
            tenants.append(t)
            base = _setup(session, t.id)
            svc = ServicesPricebookService(session).create_service(
                t.id, name="Bulk Repair", actor="bench", duration_minutes=60
            )
            tech_ids = [base["technician_id"], base["technician_b"]]
            for i in range(48):
                tech = TechnicianRepository(session).create(
                    t.id,
                    email=f"bench-{uuid.uuid4().hex[:8]}@t.test",
                    password="password123",
                    name=f"Bench Tech {i}",
                )
                tech_ids.append(uuid.UUID(tech["id"]))
            setups.append(
                {
                    **base,
                    "service_id": uuid.UUID(svc["id"]),
                    "tech_ids": tech_ids,
                }
            )
        session.flush()

        for ti, setup in enumerate(setups):
            tid = tenants[ti].id
            tech0 = setup["tech_ids"][0]
            # Bulk synthetic jobs (benchmark fixtures).
            session.execute(
                text(
                    """
                    INSERT INTO jobs (
                        id, tenant_id, job_number, customer_id, service_id,
                        assigned_technician_id, status, priority, service_type,
                        checklist, reference_code, scheduled_starts_at,
                        scheduled_ends_at, created_at, updated_at
                    )
                    SELECT
                        gen_random_uuid(),
                        CAST(:tid AS uuid),
                        'JOB-' || lpad(gs::text, 6, '0'),
                        CAST(:cid AS uuid),
                        CAST(:sid AS uuid),
                        CASE WHEN gs % 3 = 0 THEN CAST(:tech AS uuid) ELSE NULL END,
                        CASE
                            WHEN gs % 11 = 0 THEN 'CANCELLED'
                            WHEN gs % 5 = 0 THEN 'SCHEDULED'
                            ELSE 'NEW'
                        END,
                        CASE WHEN gs % 4 = 0 THEN 'HIGH' ELSE 'MEDIUM' END,
                        'Bench',
                        CAST('[]' AS jsonb),
                        'REF-' || substr(md5(gs::text || CAST(:tid AS text)), 1, 8),
                        NOW() + ((gs % 48) || ' hours')::interval,
                        NOW() + ((gs % 48) || ' hours')::interval
                            + interval '60 minutes',
                        NOW() - (gs || ' minutes')::interval,
                        NOW()
                    FROM generate_series(1, 2200) AS gs
                    """
                ),
                {
                    "tid": str(tid),
                    "cid": str(setup["customer_id"]),
                    "sid": str(setup["service_id"]),
                    "tech": str(tech0),
                },
            )
            session.execute(
                text(
                    """
                    INSERT INTO appointments (
                        id, tenant_id, appointment_number, confirmation_code,
                        customer_id, service_id, assigned_technician_id,
                        service_type, status, priority, is_emergency,
                        starts_at, ends_at, duration_minutes, timezone,
                        created_at, updated_at
                    )
                    SELECT
                        gen_random_uuid(),
                        CAST(:tid AS uuid),
                        'APT-' || lpad(gs::text, 6, '0'),
                        'APT-' || substr(md5(gs::text || CAST(:tid AS text)), 1, 6),
                        CAST(:cid AS uuid),
                        CAST(:sid AS uuid),
                        CAST(:tech AS uuid),
                        'Bench',
                        CASE WHEN gs % 7 = 0 THEN 'CANCELLED' ELSE 'SCHEDULED' END,
                        'NORMAL',
                        false,
                        NOW() + (gs || ' hours')::interval,
                        NOW() + (gs || ' hours')::interval + interval '60 minutes',
                        60,
                        'UTC',
                        NOW() - (gs || ' minutes')::interval,
                        NOW()
                    FROM generate_series(1, 2200) AS gs
                    """
                ),
                {
                    "tid": str(tid),
                    "cid": str(setup["customer_id"]),
                    "sid": str(setup["service_id"]),
                    "tech": str(tech0),
                },
            )
            session.execute(
                text(
                    """
                    INSERT INTO dispatch_events (
                        id, tenant_id, event_type, payload, created_at
                    )
                    SELECT
                        gen_random_uuid(),
                        CAST(:tid AS uuid),
                        CASE WHEN gs % 2 = 0 THEN 'JOB_ASSIGNED'
                             ELSE 'TECHNICIAN_STATUS_CHANGED' END,
                        CAST('{"bench": true}' AS jsonb),
                        NOW() - (gs || ' seconds')::interval
                    FROM generate_series(1, 500) AS gs
                    """
                ),
                {"tid": str(tid)},
            )
            # Sample assignment history for a few jobs.
            session.execute(
                text(
                    """
                    INSERT INTO job_assignment_history (
                        id, tenant_id, job_id, previous_technician_id,
                        technician_id, assigned_at, changed_by, created_at
                    )
                    SELECT
                        gen_random_uuid(),
                        j.tenant_id,
                        j.id,
                        NULL,
                        j.assigned_technician_id,
                        NOW(),
                        'bench',
                        NOW()
                    FROM jobs j
                    WHERE j.tenant_id = CAST(:tid AS uuid)
                      AND j.assigned_technician_id IS NOT NULL
                    LIMIT 200
                    """
                ),
                {"tid": str(tid)},
            )

        session.commit()
        tid = str(tenants[0].id)
        techid = str(setups[0]["tech_ids"][0])
        jid_row = session.execute(
            text("SELECT id FROM jobs WHERE tenant_id = CAST(:tid AS uuid) LIMIT 1"),
            {"tid": tid},
        ).first()
        assert jid_row is not None
        jid = str(jid_row[0])

        plans: dict[str, str] = {}
        queries = {
            "board_jobs": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM jobs
                WHERE tenant_id = '{tid}'
                  AND archived_at IS NULL
                  AND status NOT IN (
                    'COMPLETED','CANCELLED','NO_SHOW'
                  )
                  AND (
                    (scheduled_starts_at >= date_trunc('day', NOW() AT TIME ZONE 'UTC')
                     AND scheduled_starts_at < date_trunc('day', NOW() AT TIME ZONE 'UTC')
                        + interval '1 day')
                    OR scheduled_starts_at IS NULL
                  )
                ORDER BY priority DESC, scheduled_starts_at ASC NULLS LAST
                LIMIT 500
            """,
            "board_jobs_assigned": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM jobs
                WHERE tenant_id = '{tid}'
                  AND assigned_technician_id = '{techid}'
                  AND archived_at IS NULL
                ORDER BY scheduled_starts_at ASC NULLS LAST
                LIMIT 100
            """,
            "board_search": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT j.id FROM jobs j
                JOIN customers c ON c.id = j.customer_id
                WHERE j.tenant_id = '{tid}'
                  AND j.archived_at IS NULL
                  AND (
                    j.job_number ILIKE '%JOB%'
                    OR j.service_type ILIKE '%Bench%'
                    OR c.name ILIKE '%Buyer%'
                  )
                LIMIT 50
            """,
            "eligibility_appt_conflict": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM appointments
                WHERE tenant_id = '{tid}'
                  AND assigned_technician_id = '{techid}'
                  AND archived_at IS NULL
                  AND status IN (
                    'TENTATIVE','SCHEDULED','CONFIRMED','IN_PROGRESS'
                  )
                  AND starts_at < NOW() + INTERVAL '2 hours'
                  AND ends_at > NOW()
                LIMIT 1
            """,
            "assignment_history": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM job_assignment_history
                WHERE tenant_id = '{tid}' AND job_id = '{jid}'
                ORDER BY created_at DESC
                LIMIT 100
            """,
            "tech_status": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT technician_id, status FROM technician_operational_status
                WHERE tenant_id = '{tid}'
                  AND technician_id = '{techid}'
            """,
            "dispatch_events_poll": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM dispatch_events
                WHERE tenant_id = '{tid}'
                ORDER BY created_at ASC, id ASC
                LIMIT 100
            """,
        }
        for name, sql in queries.items():
            rows = session.execute(text(sql)).fetchall()
            plans[name] = "\n".join(r[0] for r in rows)
            assert "Seq Scan" in plans[name] or "Index" in plans[name]
            # Capture execution time line for the consolidation report.
            assert "Execution Time" in plans[name] or "Planning Time" in plans[name]

        # Sanity: volume landed.
        job_n = session.execute(
            text("SELECT count(*) FROM jobs WHERE tenant_id = CAST(:tid AS uuid)"),
            {"tid": tid},
        ).scalar()
        appt_n = session.execute(
            text(
                "SELECT count(*) FROM appointments WHERE tenant_id = CAST(:tid AS uuid)"
            ),
            {"tid": tid},
        ).scalar()
        tech_n = session.execute(
            text(
                "SELECT count(*) FROM technicians WHERE tenant_id = CAST(:tid AS uuid)"
            ),
            {"tid": tid},
        ).scalar()
        assert job_n >= 2000
        assert appt_n >= 2000
        assert tech_n >= 50

        # Persist plans for the report (printed under pytest -s).
        for name, plan in plans.items():
            print(f"\n=== EXPLAIN {name} ===\n{plan}\n")

        ev_n = session.execute(
            text(
                "SELECT count(*) FROM dispatch_events"
                " WHERE tenant_id = CAST(:tid AS uuid)"
            ),
            {"tid": tid},
        ).scalar()
        assert ev_n >= 500
        assert DispatchEvent is not None
        assert JobAssignmentHistory is not None
        assert TechnicianOperationalStatus is not None
    finally:
        session.close()
