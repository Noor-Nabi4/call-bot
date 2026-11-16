"""PostgreSQL concurrency for Phase 22 automation event/execution uniqueness."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed

import pytest
from sqlalchemy import create_engine, func, select, text
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.automations.engine import AutomationEngine
from callbot_platform.automations.events import emit_automation_event
from callbot_platform.automations.service import AutomationWorkflowService
from callbot_platform.crm.customers import CustomerService
from callbot_platform.db.models import Base, Tenant
from callbot_platform.db.models.automations import AutomationEvent, AutomationExecution

PG_URL = os.environ.get(
    "AUTOMATIONS_PG_TEST_URL",
    os.environ.get(
        "EQUIPMENT_PG_TEST_URL",
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
    reason="PostgreSQL not available for automation concurrency tests",
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


def test_concurrent_same_event_one_execution(pg_factory) -> None:
    session = pg_factory()
    try:
        tenant = Tenant(name="Auto PG", slug=f"auto-pg-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        customer = CustomerService(session).create(
            tenant.id,
            name="C",
            phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
            actor="t",
        )
        svc = AutomationWorkflowService(session)
        wf = svc.create(
            tenant.id,
            name="Task on job",
            trigger_event="JOB_COMPLETED",
            actor="t",
            definition={
                "actions": [{"type": "CREATE_TASK", "config": {"title": "Once"}}]
            },
        )
        svc.publish(tenant.id, uuid.UUID(wf["id"]), actor="t")
        svc.activate(tenant.id, uuid.UUID(wf["id"]), actor="t")
        job_id = uuid.uuid4()
        event = emit_automation_event(
            session,
            tenant_id=tenant.id,
            event_type="JOB_COMPLETED",
            source="jobs",
            entity_type="job",
            entity_id=job_id,
            payload={"customer_id": customer["id"], "job_id": str(job_id)},
            idempotency_key=f"job-completed:{job_id}",
        )
        session.commit()
        assert event is not None
        event_id = event.id
        tenant_id = tenant.id
        workflow_id = uuid.UUID(wf["id"])
    finally:
        session.close()

    def worker(_: int) -> str:
        s = pg_factory()
        try:
            ev = s.get(AutomationEvent, event_id)
            assert ev is not None
            AutomationEngine(s).process_event(ev)
            s.commit()
            return "ok"
        except Exception as exc:
            s.rollback()
            return f"err:{type(exc).__name__}"
        finally:
            s.close()

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = [f.result() for f in as_completed([pool.submit(worker, i) for i in range(8)])]
    assert results.count("ok") >= 1, results

    verify = pg_factory()
    try:
        count = verify.scalar(
            select(func.count())
            .select_from(AutomationExecution)
            .where(
                AutomationExecution.tenant_id == tenant_id,
                AutomationExecution.event_id == event_id,
                AutomationExecution.workflow_id == workflow_id,
            )
        )
        assert int(count or 0) == 1
    finally:
        verify.close()
