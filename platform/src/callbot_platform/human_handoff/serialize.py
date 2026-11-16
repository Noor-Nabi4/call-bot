"""Serialize handoff entities for API responses."""

from __future__ import annotations

from typing import Any

from callbot_platform.db.models.human_handoff import (
    HandoffAssignment,
    HandoffHistory,
    HandoffRequest,
)


def serialize_handoff(
    row: HandoffRequest,
    *,
    include_snapshot: bool = True,
    assignment: HandoffAssignment | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "channel": row.channel,
        "status": row.status,
        "reason": row.reason,
        "priority": row.priority,
        "customer_id": str(row.customer_id) if row.customer_id else None,
        "call_id": str(row.call_id) if row.call_id else None,
        "conversation_id": str(row.conversation_id) if row.conversation_id else None,
        "job_id": str(row.job_id) if row.job_id else None,
        "appointment_id": str(row.appointment_id) if row.appointment_id else None,
        "department_id": str(row.department_id) if row.department_id else None,
        "department": row.department,
        "intent": row.intent,
        "summary": row.summary,
        "target_user_id": str(row.target_user_id) if row.target_user_id else None,
        "target_technician_id": (
            str(row.target_technician_id) if row.target_technician_id else None
        ),
        "requested_at": row.requested_at.isoformat() if row.requested_at else None,
        "connected_at": row.connected_at.isoformat() if row.connected_at else None,
        "completed_at": row.completed_at.isoformat() if row.completed_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if include_snapshot:
        data["context_snapshot"] = dict(row.context_snapshot or {})
    if assignment is not None:
        data["assignment"] = serialize_assignment(assignment)
    return data


def serialize_assignment(row: HandoffAssignment) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "handoff_id": str(row.handoff_id),
        "assignment_type": row.assignment_type,
        "status": row.status,
        "assigned_user_id": str(row.assigned_user_id) if row.assigned_user_id else None,
        "assigned_technician_id": (
            str(row.assigned_technician_id) if row.assigned_technician_id else None
        ),
        "department_id": str(row.department_id) if row.department_id else None,
        "assigned_at": row.assigned_at.isoformat() if row.assigned_at else None,
        "accepted_at": row.accepted_at.isoformat() if row.accepted_at else None,
        "rejected_at": row.rejected_at.isoformat() if row.rejected_at else None,
        "timeout_at": row.timeout_at.isoformat() if row.timeout_at else None,
    }


def serialize_history(row: HandoffHistory) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "handoff_id": str(row.handoff_id),
        "event_type": row.event_type,
        "payload": dict(row.payload or {}),
        "actor": row.actor,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
