"""Tenant handoff / follow-up queue repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models import Call
from callbot_platform.db.models.queue import CallQueueItem
from callbot_platform.telephony.audit import write_audit


class QueueError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


_OPEN_STATUSES = frozenset({"waiting", "claimed"})
_VALID_STATUS = frozenset({"waiting", "claimed", "done", "cancelled"})


class CallQueueRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def enqueue_for_call(
        self,
        tenant_id: UUID,
        call_id: UUID,
        *,
        reason: str = "handoff",
        priority: int = 0,
        actor: str = "system",
    ) -> dict[str, Any] | None:
        """Create a queue item for a call if one does not already exist."""
        call = self._session.scalar(
            select(Call).where(Call.id == call_id, Call.tenant_id == tenant_id)
        )
        if call is None:
            raise QueueError("call_not_found", "Call not found for tenant")

        existing = self._session.scalar(
            select(CallQueueItem).where(
                CallQueueItem.tenant_id == tenant_id,
                CallQueueItem.call_id == call_id,
            )
        )
        if existing is not None:
            return self._serialize(existing, call)

        item = CallQueueItem(
            tenant_id=tenant_id,
            call_id=call_id,
            status="waiting",
            reason=(reason or "handoff").strip()[:64] or "handoff",
            priority=max(0, min(int(priority), 100)),
        )
        self._session.add(item)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="call_queue_enqueued",
            resource_ids={"queue_item_id": str(item.id), "call_id": str(call_id)},
            payload_summary={"reason": item.reason},
        )
        return self._serialize(item, call)

    def list_items(
        self,
        tenant_id: UUID,
        *,
        status: str | None = None,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        stmt = select(CallQueueItem).where(CallQueueItem.tenant_id == tenant_id)
        if status is not None:
            normalized = status.strip().lower()
            if normalized not in _VALID_STATUS:
                raise QueueError("invalid_status", "Invalid queue status filter")
            stmt = stmt.where(CallQueueItem.status == normalized)
        rows = self._session.scalars(
            stmt.order_by(
                CallQueueItem.priority.desc(),
                CallQueueItem.created_at.asc(),
            ).limit(max(1, min(limit, 100)))
        ).all()
        call_ids = [r.call_id for r in rows]
        calls: dict[UUID, Call] = {}
        if call_ids:
            for c in self._session.scalars(
                select(Call).where(Call.tenant_id == tenant_id, Call.id.in_(call_ids))
            ).all():
                calls[c.id] = c
        return [self._serialize(r, calls.get(r.call_id)) for r in rows]

    def claim(self, tenant_id: UUID, item_id: UUID, *, actor: str) -> dict[str, Any]:
        item = self._get(tenant_id, item_id)
        if item.status not in _OPEN_STATUSES:
            raise QueueError("queue_item_closed", "Queue item is already closed")
        item.status = "claimed"
        item.claimed_by = actor[:255]
        item.claimed_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="call_queue_claimed",
            resource_ids={"queue_item_id": str(item.id), "call_id": str(item.call_id)},
        )
        call = self._session.get(Call, item.call_id)
        return self._serialize(item, call)

    def complete(
        self,
        tenant_id: UUID,
        item_id: UUID,
        *,
        actor: str,
        notes: str | None = None,
        cancel: bool = False,
    ) -> dict[str, Any]:
        item = self._get(tenant_id, item_id)
        if item.status not in _OPEN_STATUSES:
            raise QueueError("queue_item_closed", "Queue item is already closed")
        item.status = "cancelled" if cancel else "done"
        item.completed_at = datetime.now(UTC)
        if notes is not None:
            item.notes = notes.strip()[:2000] or None
        if item.claimed_by is None:
            item.claimed_by = actor[:255]
            item.claimed_at = item.completed_at
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="call_queue_completed",
            resource_ids={"queue_item_id": str(item.id), "call_id": str(item.call_id)},
            payload_summary={"status": item.status},
        )
        call = self._session.get(Call, item.call_id)
        return self._serialize(item, call)

    def _get(self, tenant_id: UUID, item_id: UUID) -> CallQueueItem:
        item = self._session.scalar(
            select(CallQueueItem).where(
                CallQueueItem.id == item_id, CallQueueItem.tenant_id == tenant_id
            )
        )
        if item is None:
            raise QueueError("queue_item_not_found", "Queue item not found")
        return item

    def _serialize(self, item: CallQueueItem, call: Call | None) -> dict[str, Any]:
        return {
            "id": str(item.id),
            "call_id": str(item.call_id),
            "status": item.status,
            "reason": item.reason,
            "priority": item.priority,
            "notes": item.notes,
            "claimed_by": item.claimed_by,
            "claimed_at": item.claimed_at.isoformat() if item.claimed_at else None,
            "completed_at": (
                item.completed_at.isoformat() if item.completed_at else None
            ),
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "caller_number": call.caller_number if call else None,
            "called_number": call.called_number if call else None,
            "call_status": call.status if call else None,
        }
