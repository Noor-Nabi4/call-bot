"""Phase 22 Automation Engine: workflows, conditions, actions, idempotency, loops."""

from __future__ import annotations

import uuid

import pytest
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.automations.constants import AutomationEventType
from callbot_platform.automations.engine import AutomationEngine
from callbot_platform.automations.events import emit_automation_event
from callbot_platform.automations.publishers import publish_job_completed
from callbot_platform.automations.service import AutomationWorkflowService
from callbot_platform.crm.customers import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.jobs import JobService
from callbot_platform.db.models import Tenant
from callbot_platform.db.models.automations import (
    AutomationEvent,
    AutomationExecution,
    AutomationTask,
)
from callbot_platform.db.models.scheduling import NotificationOutbox


def _customer(session: Session, tenant_id: uuid.UUID) -> uuid.UUID:
    row = CustomerService(session).create(
        tenant_id,
        name="Auto Customer",
        phone=f"+1555{uuid.uuid4().int % 10_000_000:07d}",
        email=f"auto-{uuid.uuid4().hex[:6]}@example.test",
        actor="t",
    )
    return uuid.UUID(row["id"])


def _workflow(
    session: Session,
    tenant_id: uuid.UUID,
    *,
    trigger: str,
    actions: list[dict],
    conditions: dict | None = None,
) -> dict:
    svc = AutomationWorkflowService(session)
    wf = svc.create(
        tenant_id,
        name=f"WF-{uuid.uuid4().hex[:8]}",
        trigger_event=trigger,
        actor="t",
        definition={"conditions": conditions, "actions": actions},
    )
    svc.publish(tenant_id, uuid.UUID(wf["id"]), actor="t")
    return svc.activate(tenant_id, uuid.UUID(wf["id"]), actor="t")


def test_workflow_lifecycle_and_create_task(session: Session, tenant: Tenant) -> None:
    customer_id = _customer(session, tenant.id)
    wf = _workflow(
        session,
        tenant.id,
        trigger=AutomationEventType.JOB_COMPLETED.value,
        actions=[
            {
                "type": "CREATE_TASK",
                "config": {"title": "Follow up", "due_hours": 12},
            }
        ],
    )
    job = JobService(session).create(
        tenant.id,
        customer_id=customer_id,
        actor="t",
        service_type="Repair",
    )
    publish_job_completed(
        session,
        tenant_id=tenant.id,
        job_id=uuid.UUID(job["id"]),
        customer_id=customer_id,
        job_number=job["job_number"],
    )
    session.flush()
    event = session.scalar(
        select(AutomationEvent).where(
            AutomationEvent.tenant_id == tenant.id,
            AutomationEvent.event_type == "JOB_COMPLETED",
        )
    )
    assert event is not None
    AutomationEngine(session).process_event(event)
    session.flush()
    tasks = list(
        session.scalars(
            select(AutomationTask).where(AutomationTask.tenant_id == tenant.id)
        ).all()
    )
    assert len(tasks) == 1
    assert tasks[0].title == "Follow up"

    # Idempotent reprocess
    AutomationEngine(session).process_event(event)
    session.flush()
    count = session.scalar(
        select(func.count())
        .select_from(AutomationExecution)
        .where(
            AutomationExecution.tenant_id == tenant.id,
            AutomationExecution.workflow_id == uuid.UUID(wf["id"]),
        )
    )
    assert int(count or 0) == 1


def test_condition_gate_and_sms_enqueue(session: Session, tenant: Tenant) -> None:
    customer_id = _customer(session, tenant.id)
    _workflow(
        session,
        tenant.id,
        trigger=AutomationEventType.JOB_COMPLETED.value,
        conditions={
            "op": "ALL",
            "conditions": [
                {
                    "field": "job.status",
                    "operator": "equals",
                    "value": "COMPLETED",
                }
            ],
        },
        actions=[
            {
                "type": "SEND_SMS",
                "config": {"body": "Hi {{customer.name}}, job done."},
            }
        ],
    )
    job = JobService(session).create(
        tenant.id, customer_id=customer_id, actor="t", service_type="Tune"
    )
    event = emit_automation_event(
        session,
        tenant_id=tenant.id,
        event_type="JOB_COMPLETED",
        source="jobs",
        entity_type="job",
        entity_id=uuid.UUID(job["id"]),
        payload={
            "job_id": job["id"],
            "customer_id": str(customer_id),
            "job_number": job["job_number"],
            "job_status": "COMPLETED",
        },
        idempotency_key=f"test-job-done:{job['id']}",
    )
    assert event is not None
    AutomationEngine(session).process_event(event)
    session.flush()
    outbox = list(
        session.scalars(
            select(NotificationOutbox).where(
                NotificationOutbox.tenant_id == tenant.id,
                NotificationOutbox.channel == "sms",
            )
        ).all()
    )
    assert len(outbox) == 1


def test_self_trigger_create_job_rejected(session: Session, tenant: Tenant) -> None:
    svc = AutomationWorkflowService(session)
    with pytest.raises(CrmError) as exc:
        svc.create(
            tenant.id,
            name="Loop",
            trigger_event="JOB_CREATED",
            actor="t",
            definition={
                "actions": [{"type": "CREATE_JOB", "config": {"service_type": "Loop"}}]
            },
        )
    assert exc.value.code == "invalid_workflow"


def test_worker_processes_pending_event(session: Session, tenant: Tenant) -> None:
    customer_id = _customer(session, tenant.id)
    _workflow(
        session,
        tenant.id,
        trigger="LEAD_CREATED",
        actions=[{"type": "CREATE_TASK", "config": {"title": "New lead"}}],
    )
    from callbot_platform.automations.publishers import publish_lead_created

    lead_id = uuid.uuid4()
    publish_lead_created(
        session, tenant_id=tenant.id, lead_id=lead_id, customer_id=customer_id
    )
    session.flush()
    event = session.scalar(
        select(AutomationEvent).where(AutomationEvent.entity_id == lead_id)
    )
    assert event is not None
    AutomationEngine(session).process_event(event)
    session.flush()
    assert (
        session.scalar(
            select(func.count())
            .select_from(AutomationTask)
            .where(AutomationTask.tenant_id == tenant.id)
        )
        == 1
    )


def test_duplicate_event_idempotency(session: Session, tenant: Tenant) -> None:
    eid = uuid.uuid4()
    a = emit_automation_event(
        session,
        tenant_id=tenant.id,
        event_type="CALL_COMPLETED",
        source="calls",
        entity_type="call",
        entity_id=eid,
        payload={},
        idempotency_key=f"call-completed:{eid}",
    )
    b = emit_automation_event(
        session,
        tenant_id=tenant.id,
        event_type="CALL_COMPLETED",
        source="calls",
        entity_type="call",
        entity_id=eid,
        payload={},
        idempotency_key=f"call-completed:{eid}",
    )
    assert a is not None and b is not None
    assert a.id == b.id
