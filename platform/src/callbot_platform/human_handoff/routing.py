"""Handoff routing engine (Phase 24.3)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.human_handoff.constants import (
    AssignmentType,
    HandoffPriority,
    HandoffReason,
)
from callbot_platform.human_handoff.departments import DepartmentService
from callbot_platform.human_handoff.hours import HandoffHoursService


@dataclass(frozen=True)
class RoutingDecision:
    assignment_type: str
    priority: str
    reason: str
    department_id: UUID | None
    department_slug: str | None
    target_user_id: UUID | None
    target_technician_id: UUID | None
    queue_key: str
    after_hours: bool
    emergency: bool
    notes: str


class HandoffRoutingService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._departments = DepartmentService(session)
        self._hours = HandoffHoursService(session)

    def decide(
        self,
        *,
        tenant_id: UUID,
        snapshot: dict[str, Any],
        requested_department: str | None = None,
        target_user_id: UUID | None = None,
        target_technician_id: UUID | None = None,
        base_reason: str = HandoffReason.AI_REQUEST.value,
    ) -> RoutingDecision:
        emergency = bool((snapshot.get("emergency") or {}).get("emergency"))
        hours = snapshot.get("business_hours") or self._hours.status_at(tenant_id)
        after_hours = bool(hours.get("after_hours"))

        priority = HandoffPriority.NORMAL.value
        reason = base_reason
        dept_slug = (
            requested_department or snapshot.get("department") or ""
        ).strip().lower() or None
        department = (
            self._departments.get_by_slug(tenant_id, dept_slug) if dept_slug else None
        )

        if emergency:
            priority = HandoffPriority.EMERGENCY.value
            reason = HandoffReason.EMERGENCY.value
            emergency_dept = self._departments.get_by_slug(tenant_id, "emergency")
            return RoutingDecision(
                assignment_type=AssignmentType.DEPARTMENT.value
                if emergency_dept
                else AssignmentType.QUEUE.value,
                priority=priority,
                reason=reason,
                department_id=emergency_dept.id if emergency_dept else None,
                department_slug="emergency",
                target_user_id=None,
                target_technician_id=None,
                queue_key="emergency",
                after_hours=after_hours,
                emergency=True,
                notes="emergency_queue",
            )

        if target_technician_id is not None:
            return RoutingDecision(
                assignment_type=AssignmentType.TECHNICIAN.value,
                priority=HandoffPriority.HIGH.value,
                reason=base_reason,
                department_id=department.id if department else None,
                department_slug=department.slug if department else dept_slug,
                target_user_id=None,
                target_technician_id=target_technician_id,
                queue_key="technician",
                after_hours=after_hours,
                emergency=False,
                notes="technician_target",
            )

        if target_user_id is not None:
            return RoutingDecision(
                assignment_type=AssignmentType.USER.value,
                priority=HandoffPriority.HIGH.value,
                reason=base_reason,
                department_id=department.id if department else None,
                department_slug=department.slug if department else dept_slug,
                target_user_id=target_user_id,
                target_technician_id=None,
                queue_key="user",
                after_hours=after_hours,
                emergency=False,
                notes="user_target",
            )

        if department is not None:
            return RoutingDecision(
                assignment_type=AssignmentType.DEPARTMENT.value,
                priority=priority,
                reason=base_reason,
                department_id=department.id,
                department_slug=department.slug,
                target_user_id=None,
                target_technician_id=None,
                queue_key=f"department:{department.slug}",
                after_hours=after_hours,
                emergency=False,
                notes="department_route",
            )

        if after_hours:
            return RoutingDecision(
                assignment_type=AssignmentType.QUEUE.value,
                priority=HandoffPriority.HIGH.value,
                reason=HandoffReason.AFTER_HOURS.value,
                department_id=None,
                department_slug=dept_slug,
                target_user_id=None,
                target_technician_id=None,
                queue_key="after_hours",
                after_hours=True,
                emergency=False,
                notes="after_hours_queue",
            )

        return RoutingDecision(
            assignment_type=AssignmentType.QUEUE.value,
            priority=priority,
            reason=base_reason,
            department_id=None,
            department_slug=dept_slug,
            target_user_id=None,
            target_technician_id=None,
            queue_key="default",
            after_hours=False,
            emergency=False,
            notes="default_queue",
        )
