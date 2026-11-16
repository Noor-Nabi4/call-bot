"""Workflow CRUD, publish, activate, execution history."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.automations.actions import validate_action_config
from callbot_platform.automations.conditions import validate_condition_tree
from callbot_platform.automations.constants import (
    ACTION_TYPES,
    EVENT_TYPES,
    ActionType,
    VersionStatus,
    WorkflowStatus,
)
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models.automations import (
    AutomationExecution,
    AutomationWorkflow,
    AutomationWorkflowVersion,
)
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


def _serialize_workflow(
    row: AutomationWorkflow, *, version: AutomationWorkflowVersion | None = None
) -> dict[str, Any]:
    active = version
    payload: dict[str, Any] = {
        "id": str(row.id),
        "name": row.name,
        "description": row.description,
        "status": row.status,
        "trigger_event": row.trigger_event,
        "active_version_id": (
            str(row.active_version_id) if row.active_version_id else None
        ),
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if active is not None:
        payload["version"] = active.version
        payload["version_status"] = active.status
        payload["definition"] = active.definition
    return payload


def _serialize_execution(row: AutomationExecution) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "workflow_id": str(row.workflow_id),
        "workflow_version_id": str(row.workflow_version_id),
        "event_id": str(row.event_id),
        "status": row.status,
        "attempt": row.attempt,
        "automation_depth": row.automation_depth,
        "correlation_id": str(row.correlation_id),
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "error_code": row.error_code,
        "error_message": row.error_message,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "actions": [
            {
                "id": str(a.id),
                "action_key": a.action_key,
                "action_index": a.action_index,
                "status": a.status,
                "attempt": a.attempt,
                "error_code": a.error_code,
                "error_message": a.error_message,
                "provider_reference": a.provider_reference,
                "completed_at": a.completed_at.isoformat() if a.completed_at else None,
            }
            for a in (row.action_executions or [])
        ],
    }


class AutomationWorkflowService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def _load(self, tenant_id: UUID, workflow_id: UUID) -> AutomationWorkflow:
        row = self._session.scalar(
            select(AutomationWorkflow).where(
                AutomationWorkflow.id == workflow_id,
                AutomationWorkflow.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Workflow not found for tenant")
        return row

    def _draft_version(
        self, tenant_id: UUID, workflow: AutomationWorkflow
    ) -> AutomationWorkflowVersion:
        draft = self._session.scalar(
            select(AutomationWorkflowVersion)
            .where(
                AutomationWorkflowVersion.workflow_id == workflow.id,
                AutomationWorkflowVersion.tenant_id == tenant_id,
                AutomationWorkflowVersion.status == VersionStatus.DRAFT.value,
            )
            .order_by(AutomationWorkflowVersion.version.desc())
        )
        if draft is not None:
            return draft
        max_v = self._session.scalar(
            select(AutomationWorkflowVersion.version)
            .where(AutomationWorkflowVersion.workflow_id == workflow.id)
            .order_by(AutomationWorkflowVersion.version.desc())
            .limit(1)
        )
        next_v = int(max_v or 0) + 1
        draft = AutomationWorkflowVersion(
            tenant_id=tenant_id,
            workflow_id=workflow.id,
            version=next_v,
            status=VersionStatus.DRAFT.value,
            definition={"conditions": None, "actions": []},
        )
        self._session.add(draft)
        self._session.flush()
        return draft

    def _validate_definition(
        self, trigger_event: str, definition: dict[str, Any]
    ) -> dict[str, Any]:
        if trigger_event not in EVENT_TYPES:
            raise CrmError("invalid_trigger", f"Unknown trigger: {trigger_event}")
        conditions = definition.get("conditions")
        if conditions is not None:
            validate_condition_tree(conditions)
        actions_in = definition.get("actions") or []
        if not isinstance(actions_in, list):
            raise CrmError("invalid_definition", "actions must be a list")
        actions: list[dict[str, Any]] = []
        for raw in actions_in:
            atype = str((raw or {}).get("type") or "")
            if atype not in ACTION_TYPES:
                raise CrmError("invalid_action", f"Unknown action: {atype}")
            # Self-trigger / unsafe combos
            if trigger_event == "JOB_CREATED" and atype == ActionType.CREATE_JOB.value:
                raise CrmError(
                    "invalid_workflow",
                    "CREATE_JOB cannot be used with JOB_CREATED trigger",
                )
            if (
                trigger_event == "APPOINTMENT_CREATED"
                and atype == ActionType.CREATE_APPOINTMENT.value
            ):
                raise CrmError(
                    "invalid_workflow",
                    "CREATE_APPOINTMENT cannot be used with APPOINTMENT_CREATED",
                )
            cfg = validate_action_config(atype, (raw or {}).get("config"))
            actions.append({"type": atype, "config": cfg})
        return {"conditions": conditions, "actions": actions}

    def list(
        self, tenant_id: UUID, *, include_archived: bool = False
    ) -> dict[str, Any]:
        q = select(AutomationWorkflow).where(AutomationWorkflow.tenant_id == tenant_id)
        if not include_archived:
            q = q.where(AutomationWorkflow.status != WorkflowStatus.ARCHIVED.value)
        rows = list(
            self._session.scalars(
                q.order_by(AutomationWorkflow.updated_at.desc())
            ).all()
        )
        out = []
        for row in rows:
            version = None
            if row.active_version_id:
                version = self._session.get(
                    AutomationWorkflowVersion, row.active_version_id
                )
            else:
                version = self._session.scalar(
                    select(AutomationWorkflowVersion)
                    .where(AutomationWorkflowVersion.workflow_id == row.id)
                    .order_by(AutomationWorkflowVersion.version.desc())
                    .limit(1)
                )
            out.append(_serialize_workflow(row, version=version))
        return {"workflows": out}

    def get(self, tenant_id: UUID, workflow_id: UUID) -> dict[str, Any]:
        row = self._load(tenant_id, workflow_id)
        version = None
        if row.active_version_id:
            version = self._session.get(
                AutomationWorkflowVersion, row.active_version_id
            )
        if version is None:
            version = self._draft_version(tenant_id, row)
        return _serialize_workflow(row, version=version)

    def create(
        self,
        tenant_id: UUID,
        *,
        name: str,
        trigger_event: str,
        actor: str,
        description: str | None = None,
        definition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        cleaned = (name or "").strip()
        if not cleaned:
            raise CrmError("invalid_name", "Name is required")
        if trigger_event not in EVENT_TYPES:
            raise CrmError("invalid_trigger", f"Unknown trigger: {trigger_event}")
        defn = self._validate_definition(trigger_event, definition or {"actions": []})
        row = AutomationWorkflow(
            tenant_id=tenant_id,
            name=cleaned[:128],
            description=(description or "").strip() or None,
            status=WorkflowStatus.DRAFT.value,
            trigger_event=trigger_event,
            created_by=actor,
            updated_by=actor,
        )
        self._session.add(row)
        self._session.flush()
        version = AutomationWorkflowVersion(
            tenant_id=tenant_id,
            workflow_id=row.id,
            version=1,
            status=VersionStatus.DRAFT.value,
            definition=defn,
            created_by=actor,
        )
        self._session.add(version)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="automation.created",
            resource_ids={"workflow_id": str(row.id)},
            payload_summary={"trigger_event": trigger_event},
        )
        return _serialize_workflow(row, version=version)

    def update(
        self,
        tenant_id: UUID,
        workflow_id: UUID,
        *,
        actor: str,
        name: str | None = None,
        description: str | None = None,
        trigger_event: str | None = None,
        definition: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        row = self._load(tenant_id, workflow_id)
        if row.status == WorkflowStatus.ARCHIVED.value:
            raise CrmError("workflow_archived", "Archived workflows cannot be edited")
        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise CrmError("invalid_name", "Name is required")
            row.name = cleaned[:128]
        if description is not None:
            row.description = description.strip() or None
        if trigger_event is not None:
            if trigger_event not in EVENT_TYPES:
                raise CrmError("invalid_trigger", f"Unknown trigger: {trigger_event}")
            row.trigger_event = trigger_event
        draft = self._draft_version(tenant_id, row)
        if definition is not None:
            draft.definition = self._validate_definition(row.trigger_event, definition)
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="automation.updated",
            resource_ids={"workflow_id": str(row.id)},
            payload_summary={},
        )
        return _serialize_workflow(row, version=draft)

    def publish(
        self, tenant_id: UUID, workflow_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._load(tenant_id, workflow_id)
        draft = self._draft_version(tenant_id, row)
        draft.definition = self._validate_definition(
            row.trigger_event, draft.definition
        )
        if not (draft.definition.get("actions") or []):
            raise CrmError(
                "invalid_definition", "At least one action is required to publish"
            )
        # Supersede previous published
        prev = self._session.scalars(
            select(AutomationWorkflowVersion).where(
                AutomationWorkflowVersion.workflow_id == row.id,
                AutomationWorkflowVersion.status == VersionStatus.PUBLISHED.value,
            )
        ).all()
        for p in prev:
            p.status = VersionStatus.SUPERSEDED.value
        draft.status = VersionStatus.PUBLISHED.value
        draft.published_at = datetime.now(UTC)
        draft.created_by = actor
        row.active_version_id = draft.id
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="automation.published",
            resource_ids={
                "workflow_id": str(row.id),
                "version_id": str(draft.id),
                "version": draft.version,
            },
            payload_summary={},
        )
        return _serialize_workflow(row, version=draft)

    def activate(
        self, tenant_id: UUID, workflow_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._load(tenant_id, workflow_id)
        if row.active_version_id is None:
            raise CrmError("not_published", "Publish a version before activating")
        version = self._session.get(AutomationWorkflowVersion, row.active_version_id)
        if version is None or version.status != VersionStatus.PUBLISHED.value:
            raise CrmError("not_published", "Active version must be published")
        row.status = WorkflowStatus.ACTIVE.value
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="automation.activated",
            resource_ids={"workflow_id": str(row.id)},
            payload_summary={},
        )
        return _serialize_workflow(row, version=version)

    def disable(
        self, tenant_id: UUID, workflow_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._load(tenant_id, workflow_id)
        row.status = WorkflowStatus.DISABLED.value
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="automation.disabled",
            resource_ids={"workflow_id": str(row.id)},
            payload_summary={},
        )
        version = (
            self._session.get(AutomationWorkflowVersion, row.active_version_id)
            if row.active_version_id
            else None
        )
        return _serialize_workflow(row, version=version)

    def archive(
        self, tenant_id: UUID, workflow_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._load(tenant_id, workflow_id)
        row.status = WorkflowStatus.ARCHIVED.value
        row.archived_at = datetime.now(UTC)
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="automation.archived",
            resource_ids={"workflow_id": str(row.id)},
            payload_summary={},
        )
        return _serialize_workflow(row)

    def list_executions(
        self,
        tenant_id: UUID,
        workflow_id: UUID,
        *,
        status: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        self._load(tenant_id, workflow_id)
        q = (
            select(AutomationExecution)
            .where(
                AutomationExecution.tenant_id == tenant_id,
                AutomationExecution.workflow_id == workflow_id,
            )
            .options(selectinload(AutomationExecution.action_executions))
            .order_by(AutomationExecution.created_at.desc())
        )
        if status:
            q = q.where(AutomationExecution.status == status.strip().upper())
        rows = list(
            self._session.scalars(q.offset(max(0, offset)).limit(min(limit, 100))).all()
        )
        return {"executions": [_serialize_execution(r) for r in rows]}

    def get_execution(self, tenant_id: UUID, execution_id: UUID) -> dict[str, Any]:
        row = self._session.scalar(
            select(AutomationExecution)
            .where(
                AutomationExecution.id == execution_id,
                AutomationExecution.tenant_id == tenant_id,
            )
            .options(selectinload(AutomationExecution.action_executions))
        )
        if row is None:
            raise CrmError("not_found", "Execution not found for tenant")
        return _serialize_execution(row)
