"""Human Handoff facade: create, route, assign, accept, complete."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.automations.publishers import (
    publish_handoff_assigned,
    publish_handoff_completed,
    publish_handoff_connected,
    publish_handoff_created,
)
from callbot_platform.db.models.human_handoff import (
    HandoffAssignment,
    HandoffHistory,
    HandoffRequest,
)
from callbot_platform.handoff.repos import HandoffRepository
from callbot_platform.human_handoff.constants import (
    LEGACY_REASON_MAP,
    AssignmentStatus,
    AssignmentType,
    HandoffChannel,
    HandoffPriority,
    HandoffReason,
    HandoffStatus,
    HistoryEvent,
)
from callbot_platform.human_handoff.context import HandoffContextService
from callbot_platform.human_handoff.departments import DepartmentService
from callbot_platform.human_handoff.errors import HandoffDomainError
from callbot_platform.human_handoff.routing import HandoffRoutingService
from callbot_platform.human_handoff.serialize import (
    serialize_handoff,
    serialize_history,
)
from callbot_platform.human_handoff.telephony import (
    NoOpTransferProvider,
    TelephonyTransferProvider,
    TransferRequest,
)
from callbot_platform.scheduling.notifications import NotificationService
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class HumanHandoffService:
    def __init__(
        self,
        session: Session,
        *,
        transfer_provider: TelephonyTransferProvider | None = None,
    ) -> None:
        self._session = session
        self._context = HandoffContextService(session)
        self._routing = HandoffRoutingService(session)
        self._departments = DepartmentService(session)
        self._transfer = transfer_provider or NoOpTransferProvider()
        self._settings = HandoffRepository(session)

    def _append_history(
        self,
        *,
        tenant_id: UUID,
        handoff_id: UUID,
        event_type: str,
        actor: str | None,
        payload: dict[str, Any] | None = None,
    ) -> None:
        self._session.add(
            HandoffHistory(
                tenant_id=tenant_id,
                handoff_id=handoff_id,
                event_type=event_type,
                actor=actor,
                payload=payload or {},
            )
        )

    def _normalize_reason(self, reason: str | None) -> str:
        if not reason:
            return HandoffReason.AI_REQUEST.value
        raw = reason.strip()
        if raw.upper() in {e.value for e in HandoffReason}:
            return raw.upper()
        return LEGACY_REASON_MAP.get(raw.lower(), HandoffReason.AI_REQUEST.value)

    def create_request(
        self,
        *,
        tenant_id: UUID,
        channel: str,
        actor: str,
        reason: str | None = None,
        summary: str | None = None,
        department: str | None = None,
        emergency: bool = False,
        call_id: UUID | None = None,
        conversation_id: UUID | None = None,
        customer_id: UUID | None = None,
        job_id: UUID | None = None,
        appointment_id: UUID | None = None,
        target_user_id: UUID | None = None,
        target_technician_id: UUID | None = None,
        idempotency_key: str | None = None,
        notify: bool = True,
    ) -> dict[str, Any]:
        channel_u = channel.upper()
        if channel_u not in {e.value for e in HandoffChannel}:
            raise HandoffDomainError("invalid_channel", "Invalid handoff channel")

        if idempotency_key:
            existing = self._session.scalar(
                select(HandoffRequest).where(
                    HandoffRequest.tenant_id == tenant_id,
                    HandoffRequest.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return serialize_handoff(existing)

        settings = self._settings.get(tenant_id)
        if channel_u == HandoffChannel.VOICE.value and not settings.get("enabled"):
            raise HandoffDomainError(
                "handoff_disabled", "Voice handoff is disabled for tenant"
            )

        snapshot = self._context.build_snapshot(
            tenant_id=tenant_id,
            call_id=call_id,
            conversation_id=conversation_id,
            customer_id=customer_id,
            summary=summary,
            transfer_reason=reason,
            department=department,
            explicit_emergency=emergency,
            actor=actor,
        )
        if customer_id is None and snapshot.get("customer"):
            customer_id = UUID(str(snapshot["customer"]["id"]))

        decision = self._routing.decide(
            tenant_id=tenant_id,
            snapshot=snapshot,
            requested_department=department,
            target_user_id=target_user_id,
            target_technician_id=target_technician_id,
            base_reason=self._normalize_reason(reason),
        )

        # Prefer open job/appointment from snapshot when not provided
        if job_id is None and snapshot.get("jobs"):
            job_id = UUID(str(snapshot["jobs"][0]["id"]))
        if appointment_id is None and snapshot.get("appointments"):
            appointment_id = UUID(str(snapshot["appointments"][0]["id"]))

        now = datetime.now(UTC)
        row = HandoffRequest(
            tenant_id=tenant_id,
            channel=channel_u,
            status=HandoffStatus.ROUTING.value,
            reason=decision.reason,
            priority=decision.priority,
            customer_id=customer_id,
            call_id=call_id,
            conversation_id=conversation_id,
            job_id=job_id,
            appointment_id=appointment_id,
            department_id=decision.department_id,
            department=decision.department_slug,
            intent=snapshot.get("intent"),
            summary=snapshot.get("summary") or summary,
            target_user_id=decision.target_user_id,
            target_technician_id=decision.target_technician_id,
            context_snapshot=snapshot,
            idempotency_key=idempotency_key,
            requested_at=now,
        )
        try:
            with self._session.begin_nested():
                self._session.add(row)
                self._session.flush()
        except IntegrityError:
            self._session.expire_all()
            if idempotency_key:
                again = self._session.scalar(
                    select(HandoffRequest).where(
                        HandoffRequest.tenant_id == tenant_id,
                        HandoffRequest.idempotency_key == idempotency_key,
                    )
                )
                if again is not None:
                    return serialize_handoff(again)
            raise HandoffDomainError(
                "handoff_conflict", "Handoff already exists"
            ) from None

        self._append_history(
            tenant_id=tenant_id,
            handoff_id=row.id,
            event_type=HistoryEvent.CREATED.value,
            actor=actor,
            payload={"channel": channel_u, "priority": decision.priority},
        )
        self._append_history(
            tenant_id=tenant_id,
            handoff_id=row.id,
            event_type=HistoryEvent.ROUTED.value,
            actor=actor,
            payload={
                "queue_key": decision.queue_key,
                "assignment_type": decision.assignment_type,
                "notes": decision.notes,
            },
        )

        assignment = HandoffAssignment(
            tenant_id=tenant_id,
            handoff_id=row.id,
            assignment_type=decision.assignment_type,
            status=AssignmentStatus.PENDING.value,
            assigned_user_id=decision.target_user_id,
            assigned_technician_id=decision.target_technician_id,
            department_id=decision.department_id,
            assigned_at=now,
        )
        try:
            with self._session.begin_nested():
                self._session.add(assignment)
                self._session.flush()
        except IntegrityError:
            self._session.expire_all()
            assignment = self._session.scalar(
                select(HandoffAssignment).where(
                    HandoffAssignment.tenant_id == tenant_id,
                    HandoffAssignment.handoff_id == row.id,
                    HandoffAssignment.status.in_(
                        [
                            AssignmentStatus.PENDING.value,
                            AssignmentStatus.ACCEPTED.value,
                        ]
                    ),
                )
            )
            if assignment is None:
                raise

        row.status = HandoffStatus.ASSIGNED.value
        row.updated_at = now
        self._append_history(
            tenant_id=tenant_id,
            handoff_id=row.id,
            event_type=HistoryEvent.ASSIGNED.value,
            actor=actor,
            payload={"assignment_id": str(assignment.id)},
        )
        self._session.flush()

        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="handoff.created",
            resource_ids={
                "handoff_id": str(row.id),
                "call_id": str(call_id) if call_id else None,
            },
            payload_summary={
                "channel": channel_u,
                "priority": row.priority,
                "department": row.department,
            },
            idempotency_key=idempotency_key,
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="handoff.assigned",
            resource_ids={
                "handoff_id": str(row.id),
                "assignment_id": str(assignment.id),
            },
            payload_summary={"assignment_type": assignment.assignment_type},
        )

        publish_handoff_created(
            self._session,
            tenant_id=tenant_id,
            handoff_id=row.id,
            channel=channel_u,
            priority=row.priority,
            customer_id=customer_id,
        )
        publish_handoff_assigned(
            self._session,
            tenant_id=tenant_id,
            handoff_id=row.id,
            assignment_id=assignment.id,
            assignment_type=assignment.assignment_type,
        )

        if notify:
            self._notify_staff(
                tenant_id=tenant_id, handoff=row, decision_notes=decision.notes
            )

        # Voice: record transfer intent via provider abstraction
        transfer_result = None
        if channel_u == HandoffChannel.VOICE.value:
            dest = None
            if decision.department_id:
                dept = self._departments.get(tenant_id, decision.department_id)
                dest = dept.phone_e164 if dept else None
            if not dest:
                dest = settings.get("escalation_phone_e164")
            transfer_result = self._transfer.transfer_call(
                TransferRequest(
                    tenant_id=str(tenant_id),
                    call_id=str(call_id) if call_id else None,
                    destination_e164=str(dest or ""),
                    mode=str(settings.get("mode") or "warm"),
                    sip_outbound_trunk_id=settings.get("sip_outbound_trunk_id"),
                    context_summary=row.summary,
                )
            )

        payload = serialize_handoff(row, assignment=assignment)
        if transfer_result is not None:
            payload["transfer"] = {
                "status": transfer_result.status,
                "provider": transfer_result.provider,
                "detail": transfer_result.detail,
            }
        return payload

    def _notify_staff(
        self,
        *,
        tenant_id: UUID,
        handoff: HandoffRequest,
        decision_notes: str,
    ) -> None:
        settings = self._settings.get(tenant_id)
        phone = settings.get("escalation_phone_e164")
        if not phone:
            return
        body = (
            f"Handoff {handoff.priority}: {handoff.summary or 'Customer needs help'} "
            f"[{handoff.channel}/{handoff.department or decision_notes}]"
        )[:480]
        try:
            NotificationService(self._session).enqueue_sms(
                tenant_id=tenant_id,
                to_address=phone,
                body=body,
                idempotency_key=f"handoff-notify:{handoff.id}",
            )
        except Exception:
            logger.exception(
                "handoff_notify_failed",
                extra={"tenant_id": str(tenant_id), "handoff_id": str(handoff.id)},
            )

    def get(self, tenant_id: UUID, handoff_id: UUID) -> dict[str, Any]:
        row = self._require(tenant_id, handoff_id)
        assignment = self._active_assignment(tenant_id, handoff_id)
        data = serialize_handoff(row, assignment=assignment)
        # Attach signed recording URL on read only
        call_id = row.call_id
        if call_id is not None:
            try:
                from callbot_platform.call_intelligence import CallIntelligenceService

                rec = CallIntelligenceService(
                    self._session
                ).recordings.presign_download(
                    tenant_id=tenant_id,
                    call_id=call_id,
                    actor="handoff_view",
                )
                snap = dict(data.get("context_snapshot") or {})
                snap["recording_url"] = rec.get("download_url")
                data["context_snapshot"] = snap
            except Exception:
                logger.exception(
                    "handoff_recording_presign_failed",
                    extra={
                        "tenant_id": str(tenant_id),
                        "handoff_id": str(handoff_id),
                    },
                )
        history = list(
            self._session.scalars(
                select(HandoffHistory)
                .where(
                    HandoffHistory.tenant_id == tenant_id,
                    HandoffHistory.handoff_id == handoff_id,
                )
                .order_by(HandoffHistory.created_at.asc())
            ).all()
        )
        data["history"] = [serialize_history(h) for h in history]
        return data

    def list(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        priority: str | None = None,
        channel: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> dict[str, Any]:
        limit = max(1, min(int(limit), 200))
        offset = max(0, int(offset))
        stmt = select(HandoffRequest).where(HandoffRequest.tenant_id == tenant_id)
        if status:
            if status.upper() == "EMERGENCY":
                stmt = stmt.where(
                    HandoffRequest.priority == HandoffPriority.EMERGENCY.value
                )
            elif status.upper() == "QUEUE":
                stmt = stmt.where(
                    HandoffRequest.status.in_(
                        [
                            HandoffStatus.PENDING.value,
                            HandoffStatus.ROUTING.value,
                            HandoffStatus.ASSIGNED.value,
                        ]
                    )
                )
            elif status.upper() == "ASSIGNED":
                stmt = stmt.where(HandoffRequest.status == HandoffStatus.ASSIGNED.value)
            elif status.upper() == "COMPLETED":
                stmt = stmt.where(
                    HandoffRequest.status == HandoffStatus.COMPLETED.value
                )
            else:
                stmt = stmt.where(HandoffRequest.status == status.upper())
        if priority:
            stmt = stmt.where(HandoffRequest.priority == priority.upper())
        if channel:
            stmt = stmt.where(HandoffRequest.channel == channel.upper())
        rows = list(
            self._session.scalars(
                stmt.order_by(
                    HandoffRequest.priority.desc(),
                    HandoffRequest.requested_at.desc(),
                )
                .limit(limit)
                .offset(offset)
            ).all()
        )
        return {
            "items": [serialize_handoff(r, include_snapshot=False) for r in rows],
            "limit": limit,
            "offset": offset,
        }

    def accept(
        self,
        tenant_id: UUID,
        handoff_id: UUID,
        *,
        actor: str,
        user_id: UUID | None = None,
    ) -> dict[str, Any]:
        row = self._require(tenant_id, handoff_id, for_update=True)
        if row.status not in {
            HandoffStatus.ASSIGNED.value,
            HandoffStatus.ROUTING.value,
            HandoffStatus.PENDING.value,
        }:
            raise HandoffDomainError("invalid_status", "Handoff cannot be accepted")
        assignment = self._active_assignment(tenant_id, handoff_id, for_update=True)
        if assignment is None:
            raise HandoffDomainError("assignment_not_found", "No pending assignment")
        if assignment.status != AssignmentStatus.PENDING.value:
            raise HandoffDomainError("already_resolved", "Assignment already resolved")

        now = datetime.now(UTC)
        assignment.status = AssignmentStatus.ACCEPTED.value
        assignment.accepted_at = now
        if user_id is not None:
            assignment.assigned_user_id = user_id
        row.status = HandoffStatus.CONNECTED.value
        row.connected_at = now
        row.updated_at = now
        self._append_history(
            tenant_id=tenant_id,
            handoff_id=handoff_id,
            event_type=HistoryEvent.CONNECTED.value,
            actor=actor,
            payload={"assignment_id": str(assignment.id)},
        )
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="handoff.connected",
            resource_ids={"handoff_id": str(handoff_id)},
            payload_summary={},
        )
        publish_handoff_connected(
            self._session, tenant_id=tenant_id, handoff_id=handoff_id
        )
        return serialize_handoff(row, assignment=assignment)

    def reject(
        self,
        tenant_id: UUID,
        handoff_id: UUID,
        *,
        actor: str,
    ) -> dict[str, Any]:
        row = self._require(tenant_id, handoff_id, for_update=True)
        assignment = self._active_assignment(tenant_id, handoff_id, for_update=True)
        if assignment is None or assignment.status != AssignmentStatus.PENDING.value:
            raise HandoffDomainError("assignment_not_found", "No pending assignment")
        now = datetime.now(UTC)
        assignment.status = AssignmentStatus.REJECTED.value
        assignment.rejected_at = now
        # Re-queue
        new_a = HandoffAssignment(
            tenant_id=tenant_id,
            handoff_id=handoff_id,
            assignment_type=AssignmentType.QUEUE.value,
            status=AssignmentStatus.PENDING.value,
            assigned_at=now,
            department_id=row.department_id,
        )
        self._session.add(new_a)
        row.status = HandoffStatus.ASSIGNED.value
        row.updated_at = now
        self._append_history(
            tenant_id=tenant_id,
            handoff_id=handoff_id,
            event_type=HistoryEvent.REJECTED.value,
            actor=actor,
            payload={"previous_assignment_id": str(assignment.id)},
        )
        self._session.flush()
        return serialize_handoff(row, assignment=new_a)

    def complete(
        self,
        tenant_id: UUID,
        handoff_id: UUID,
        *,
        actor: str,
    ) -> dict[str, Any]:
        row = self._require(tenant_id, handoff_id, for_update=True)
        if row.status == HandoffStatus.COMPLETED.value:
            return serialize_handoff(row)
        now = datetime.now(UTC)
        row.status = HandoffStatus.COMPLETED.value
        row.completed_at = now
        row.updated_at = now
        assignment = self._active_assignment(tenant_id, handoff_id, for_update=True)
        if assignment and assignment.status == AssignmentStatus.PENDING.value:
            assignment.status = AssignmentStatus.ACCEPTED.value
            assignment.accepted_at = assignment.accepted_at or now
        self._append_history(
            tenant_id=tenant_id,
            handoff_id=handoff_id,
            event_type=HistoryEvent.COMPLETED.value,
            actor=actor,
            payload={},
        )
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="handoff.completed",
            resource_ids={"handoff_id": str(handoff_id)},
            payload_summary={},
        )
        publish_handoff_completed(
            self._session, tenant_id=tenant_id, handoff_id=handoff_id
        )
        return serialize_handoff(row, assignment=assignment)

    def _require(
        self, tenant_id: UUID, handoff_id: UUID, *, for_update: bool = False
    ) -> HandoffRequest:
        stmt = select(HandoffRequest).where(
            HandoffRequest.id == handoff_id,
            HandoffRequest.tenant_id == tenant_id,
        )
        if for_update:
            stmt = stmt.with_for_update()
        row = self._session.scalar(stmt)
        if row is None:
            raise HandoffDomainError("handoff_not_found", "Handoff not found")
        return row

    def _active_assignment(
        self,
        tenant_id: UUID,
        handoff_id: UUID,
        *,
        for_update: bool = False,
    ) -> HandoffAssignment | None:
        stmt = (
            select(HandoffAssignment)
            .where(
                HandoffAssignment.tenant_id == tenant_id,
                HandoffAssignment.handoff_id == handoff_id,
                HandoffAssignment.status.in_(
                    [AssignmentStatus.PENDING.value, AssignmentStatus.ACCEPTED.value]
                ),
            )
            .order_by(HandoffAssignment.assigned_at.desc())
            .limit(1)
        )
        if for_update:
            stmt = stmt.with_for_update()
        return self._session.scalar(stmt)
