"""PostgreSQL concurrency tests for Phase 8 lead conversion/transitions.

Skip when Postgres is unavailable — SQLite cannot prove FOR UPDATE races.
"""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.leads import LeadService
from callbot_platform.db.models import Base, LeadConversion, Tenant, TenantUser
from callbot_platform.organization.membership import MEMBERSHIP_ACTIVE

PG_URL = os.environ.get(
    "LEADS_PG_TEST_URL",
    os.environ.get(
        "SERVICES_PG_TEST_URL",
        os.environ.get(
            "INVENTORY_PG_TEST_URL",
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


pytestmark = pytest.mark.skipif(
    not _pg_available(PG_URL),
    reason="PostgreSQL not available for leads concurrency tests",
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
    row = Tenant(name="Leads PG", slug=f"leads-pg-{uuid.uuid4().hex[:8]}")
    session.add(row)
    session.flush()
    return row


def test_concurrent_conversion_single_winner(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        lead = LeadService(session).create(
            tenant.id, title="Race Convert", actor="setup"
        )
        session.commit()
        lead_id = uuid.UUID(lead["id"])
        tenant_id = tenant.id
    finally:
        session.close()

    def worker(n: int) -> dict:
        s = pg_factory()
        try:
            result = LeadService(s).convert(
                tenant_id,
                lead_id,
                actor=f"worker-{n}",
                create_customer={
                    "name": f"Cust {n}",
                    "phone": f"+1555555{n:04d}",
                },
            )
            s.commit()
            return {
                "ok": True,
                "already": result["already_converted"],
                "customer_id": result["conversion"]["customer_id"],
                "created": result["conversion"]["created_customer"],
            }
        except Exception as exc:
            s.rollback()
            return {
                "ok": False,
                "error": str(exc),
                "code": getattr(exc, "code", None),
            }
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [pool.submit(worker, 101), pool.submit(worker, 102)]
        results = [f.result() for f in as_completed(futures)]

    assert all(r["ok"] for r in results), results
    winners = [r for r in results if not r["already"]]
    already = [r for r in results if r["already"]]
    assert len(winners) == 1
    assert len(already) == 1
    assert winners[0]["customer_id"] == already[0]["customer_id"]

    session = pg_factory()
    try:
        count = session.scalar(
            select(func.count())
            .select_from(LeadConversion)
            .where(LeadConversion.lead_id == lead_id)
        )
        assert count == 1
    finally:
        session.close()


def test_concurrent_status_transitions_serialized(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        lead = LeadService(session).create(
            tenant.id, title="Race Transition", actor="setup"
        )
        lid = uuid.UUID(lead["id"])
        # Advance to BOOKED so WON vs LOST are mutually exclusive winners.
        api = LeadService(session)
        api.transition_status(tenant.id, lid, to_status="QUALIFIED", actor="setup")
        api.transition_status(tenant.id, lid, to_status="CONTACTED", actor="setup")
        api.transition_status(tenant.id, lid, to_status="BOOKED", actor="setup")
        session.commit()
        lead_id = lid
        tenant_id = tenant.id
    finally:
        session.close()

    def worker(target: str) -> dict:
        s = pg_factory()
        try:
            result = LeadService(s).transition_status(
                tenant_id, lead_id, to_status=target, actor=f"t-{target}"
            )
            s.commit()
            return {"ok": True, "status": result["status"]}
        except CrmError as exc:
            s.rollback()
            return {"ok": False, "code": exc.code}
        except Exception as exc:
            s.rollback()
            return {"ok": False, "error": str(exc)}
        finally:
            s.close()

    # From BOOKED, WON and LOST are both valid; the loser of the race cannot
    # transition from the winner's terminal/peer status.
    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, "WON"),
            pool.submit(worker, "LOST"),
        ]
        results = [f.result() for f in as_completed(futures)]

    oks = [r for r in results if r.get("ok")]
    fails = [r for r in results if not r.get("ok")]
    assert len(oks) == 1, results
    assert len(fails) == 1, results
    assert fails[0].get("code") == "invalid_transition"

    session = pg_factory()
    try:
        final = LeadService(session).get(tenant_id, lead_id)
        assert final["status"] in {"WON", "LOST"}
        assert final["status"] == oks[0]["status"]
        acts = LeadService(session).list_activities(tenant_id, lead_id)
        # Three setup transitions + one race winner.
        status_changes = [
            a for a in acts["activities"] if a["activity_type"] == "STATUS_CHANGED"
        ]
        assert len(status_changes) == 4
    finally:
        session.close()


def test_concurrent_owner_assignment(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = _tenant(session)
        a = TenantUser(
            tenant_id=tenant.id,
            email="a@t.test",
            password_hash="x",
            name="A",
            role="admin",
            status=MEMBERSHIP_ACTIVE,
            is_active=True,
        )
        b = TenantUser(
            tenant_id=tenant.id,
            email="b@t.test",
            password_hash="x",
            name="B",
            role="admin",
            status=MEMBERSHIP_ACTIVE,
            is_active=True,
        )
        session.add_all([a, b])
        session.flush()
        lead = LeadService(session).create(tenant.id, title="Owner Race", actor="setup")
        session.commit()
        lead_id = uuid.UUID(lead["id"])
        tenant_id = tenant.id
        owner_a = a.id
        owner_b = b.id
    finally:
        session.close()

    def worker(owner_id: uuid.UUID, label: str) -> dict:
        s = pg_factory()
        try:
            result = LeadService(s).update(
                tenant_id,
                lead_id,
                actor=label,
                owner_user_id=owner_id,
            )
            s.commit()
            return {"ok": True, "owner": result["owner_user_id"]}
        except Exception as exc:
            s.rollback()
            return {"ok": False, "error": str(exc)}
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = [
            pool.submit(worker, owner_a, "worker-a"),
            pool.submit(worker, owner_b, "worker-b"),
        ]
        results = [f.result() for f in as_completed(futures)]

    assert all(r["ok"] for r in results), results
    session = pg_factory()
    try:
        final = LeadService(session).get(tenant_id, lead_id)
        assert final["owner_user_id"] in {str(owner_a), str(owner_b)}
        acts = LeadService(session).list_activities(tenant_id, lead_id)
        owner_changes = [
            a for a in acts["activities"] if a["activity_type"] == "OWNER_CHANGED"
        ]
        assert len(owner_changes) >= 1
    finally:
        session.close()


def test_explain_lead_hot_paths(pg_factory) -> None:
    """Capture EXPLAIN ANALYZE for hot Lead queries (evidence, not thresholds)."""
    session = pg_factory()
    try:
        tenant = _tenant(session)
        owner = TenantUser(
            tenant_id=tenant.id,
            email="explain@t.test",
            password_hash="x",
            name="Explain",
            role="admin",
            status=MEMBERSHIP_ACTIVE,
            is_active=True,
        )
        session.add(owner)
        session.flush()
        api = LeadService(session)
        for i in range(40):
            api.create(
                tenant.id,
                title=f"Explain {i}",
                source="PHONE" if i % 2 == 0 else "WEBSITE",
                owner_user_id=owner.id if i % 3 == 0 else None,
                actor="t",
            )
        session.commit()
        tid = str(tenant.id)
        oid = str(owner.id)

        plans: dict[str, str] = {}
        queries = {
            "list_cursor": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM leads
                WHERE tenant_id = '{tid}' AND archived_at IS NULL
                ORDER BY created_at DESC, id DESC
                LIMIT 50
            """,
            "status_filter": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM leads
                WHERE tenant_id = '{tid}' AND status = 'NEW' AND archived_at IS NULL
            """,
            "owner_filter": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM leads
                WHERE tenant_id = '{tid}' AND owner_user_id = '{oid}'
                  AND archived_at IS NULL
            """,
            "pipeline_group": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT status, count(*) FROM leads
                WHERE tenant_id = '{tid}' AND archived_at IS NULL
                GROUP BY status
            """,
            "text_search": f"""
                EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
                SELECT id FROM leads
                WHERE tenant_id = '{tid}' AND archived_at IS NULL
                  AND lower(title) LIKE '%explain%'
                ORDER BY created_at DESC, id DESC
                LIMIT 50
            """,
        }
        for name, sql in queries.items():
            rows = session.execute(text(sql)).fetchall()
            plans[name] = "\n".join(r[0] for r in rows)
            # Soft assertion: plan text was produced (index usage varies by stats).
            assert "Seq Scan" in plans[name] or "Index" in plans[name]
        # Keep plans in assertion message for CI evidence when debugging.
        assert all(plans.values())
    finally:
        session.close()
