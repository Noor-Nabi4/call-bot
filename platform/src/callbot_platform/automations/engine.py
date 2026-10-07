"""Match workflows and run executions for a durable automation event."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.automations.actions import ActionError, ActionExecutor
from callbot_platform.automations.conditions import evaluate_condition_node
from callbot_platform.automations.constants import (
    MAX_AUTOMATION_DEPTH,
    ActionExecutionStatus,
    ExecutionStatus,
    WorkflowStatus,
)
from callbot_platform.db.models.automations import (
    AutomationActionExecution,
    AutomationEvent,
    AutomationExecution,
    AutomationWorkflow,
    AutomationWorkflowVersion,
)
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class AutomationEngine:
    def __init__(self, session: Session) -> None:
        self._session = session

    def process_event(self, event: AutomationEvent) -> list[dict[str, Any]]:
        if event.automation_depth > MAX_AUTOMATION_DEPTH:
            event.status = "suppressed"
            event.processed_at = datetime.now(UTC)
            event.error = "max_automation_depth"
            return []

        workflows = list(
            self._session.scalars(
                select(AutomationWorkflow).where(
                    AutomationWorkflow.tenant_id == event.tenant_id,
                    AutomationWorkflow.trigger_event == event.event_type,
                    AutomationWorkflow.status == WorkflowStatus.ACTIVE.value,
                    AutomationWorkflow.archived_at.is_(None),
                )
            ).all()
        )
        results: list[dict[str, Any]] = []
        for wf in workflows:
            if wf.active_version_id is None:
                continue
            version = self._session.get(AutomationWorkflowVersion, wf.active_version_id)
            if version is None or version.tenant_id != event.tenant_id:
                continue
            logger.info(
                "automation_workflow_matched tenant_id=%s workflow_id=%s event_id=%s",
                event.tenant_id,
                wf.id,
                event.id,
            )
            results.append(self._run_workflow(event, wf, version))
        event.status = "processed"
        event.processed_at = datetime.now(UTC)
        event.updated_at = datetime.now(UTC)
        return results

    def _run_workflow(
        self,
        event: AutomationEvent,
        workflow: AutomationWorkflow,
        version: AutomationWorkflowVersion,
    ) -> dict[str, Any]:
        existing = self._session.scalar(
            select(AutomationExecution).where(
                AutomationExecution.tenant_id == event.tenant_id,
                AutomationExecution.event_id == event.id,
                AutomationExecution.workflow_id == workflow.id,
            )
        )
        if existing is not None:
            return {
                "execution_id": str(existing.id),
                "status": existing.status,
                "idempotent": True,
            }

        definition = version.definition or {}
        conditions = definition.get("conditions")
        try:
            matched = evaluate_condition_node(
                self._session,
                tenant_id=event.tenant_id,
                event=event,
                node=conditions,
            )
        except Exception as exc:
            logger.exception("condition_eval_failed")
            matched = False
            error = str(exc)
        else:
            error = None

        execution = AutomationExecution(
            tenant_id=event.tenant_id,
            workflow_id=workflow.id,
            workflow_version_id=version.id,
            event_id=event.id,
            status=ExecutionStatus.PENDING.value,
            attempt=1,
            automation_depth=event.automation_depth,
            correlation_id=event.correlation_id,
        )
        try:
            with self._session.begin_nested():
                self._session.add(execution)
                self._session.flush()
        except IntegrityError:
            existing = self._session.scalar(
                select(AutomationExecution).where(
                    AutomationExecution.tenant_id == event.tenant_id,
                    AutomationExecution.event_id == event.id,
                    AutomationExecution.workflow_id == workflow.id,
                )
            )
            if existing is None:
                raise
            return {
                "execution_id": str(existing.id),
                "status": existing.status,
                "idempotent": True,
            }

        if not matched:
            execution.status = ExecutionStatus.SUPPRESSED.value
            execution.completed_at = datetime.now(UTC)
            execution.error_code = "conditions_not_met"
            execution.error_message = error
            return {"execution_id": str(execution.id), "status": execution.status}

        execution.status = ExecutionStatus.RUNNING.value
        execution.started_at = datetime.now(UTC)
        write_audit(
            self._session,
            tenant_id=event.tenant_id,
            actor="automation",
            action="automation.execution_started",
            resource_ids={
                "execution_id": str(execution.id),
                "workflow_id": str(workflow.id),
                "event_id": str(event.id),
            },
            payload_summary={},
        )
        self._session.flush()

        actions = definition.get("actions") or []
        successes = 0
        failures = 0
        for idx, action in enumerate(actions):
            action_type = str(action.get("type") or "")
            config = dict(action.get("config") or {})
            idem = f"automation:{execution.id}:action:{idx}:{action_type}"
            action_row = AutomationActionExecution(
                tenant_id=event.tenant_id,
                execution_id=execution.id,
                action_key=action_type,
                action_index=idx,
                status=ActionExecutionStatus.RUNNING.value,
                attempt=1,
                idempotency_key=idem[:191],
                started_at=datetime.now(UTC),
                result={},
            )
            try:
                with self._session.begin_nested():
                    self._session.add(action_row)
                    self._session.flush()
            except IntegrityError:
                existing_action = self._session.scalar(
                    select(AutomationActionExecution).where(
                        AutomationActionExecution.tenant_id == event.tenant_id,
                        AutomationActionExecution.idempotency_key == idem[:191],
                    )
                )
                if (
                    existing_action
                    and existing_action.status == ActionExecutionStatus.SUCCEEDED.value
                ):
                    successes += 1
                    continue
                action_row = existing_action or action_row

            logger.info(
                "automation_action_started execution_id=%s action=%s",
                execution.id,
                action_type,
            )
            try:
                result = ActionExecutor(self._session).execute(
                    tenant_id=event.tenant_id,
                    event=event,
                    action_type=action_type,
                    config=config,
                    action_row=action_row,
                    execution_id=execution.id,
                )
                action_row.status = ActionExecutionStatus.SUCCEEDED.value
                action_row.result = result
                action_row.completed_at = datetime.now(UTC)
                action_row.provider_reference = (
                    str(
                        result.get("notification_id")
                        or result.get("job_id")
                        or result.get("task_id")
                        or result.get("appointment_id")
                        or ""
                    )[:255]
                    or None
                )
                successes += 1
                logger.info(
                    "automation_action_succeeded execution_id=%s action=%s",
                    execution.id,
                    action_type,
                )
            except ActionError as exc:
                action_row.status = ActionExecutionStatus.FAILED.value
                action_row.error_code = exc.code
                action_row.error_message = str(exc)[:2000]
                action_row.completed_at = datetime.now(UTC)
                failures += 1
                write_audit(
                    self._session,
                    tenant_id=event.tenant_id,
                    actor="automation",
                    action="automation.action_failed",
                    resource_ids={
                        "execution_id": str(execution.id),
                        "action": action_type,
                    },
                    payload_summary={"code": exc.code},
                )
                logger.warning(
                    "automation_action_failed execution_id=%s action=%s code=%s",
                    execution.id,
                    action_type,
                    exc.code,
                )
            except Exception as exc:
                action_row.status = ActionExecutionStatus.FAILED.value
                action_row.error_code = "action_error"
                action_row.error_message = str(exc)[:2000]
                action_row.completed_at = datetime.now(UTC)
                failures += 1
                logger.exception("automation_action_error")

        if failures == 0:
            execution.status = ExecutionStatus.SUCCEEDED.value
            audit_action = "automation.execution_succeeded"
        elif successes == 0:
            execution.status = ExecutionStatus.FAILED.value
            audit_action = "automation.execution_failed"
            execution.error_code = "all_actions_failed"
        else:
            execution.status = ExecutionStatus.PARTIAL_SUCCESS.value
            audit_action = "automation.execution_succeeded"
            execution.error_code = "partial_success"
        execution.completed_at = datetime.now(UTC)
        execution.updated_at = datetime.now(UTC)
        write_audit(
            self._session,
            tenant_id=event.tenant_id,
            actor="automation",
            action=audit_action,
            resource_ids={"execution_id": str(execution.id)},
            payload_summary={"status": execution.status},
        )
        return {"execution_id": str(execution.id), "status": execution.status}
