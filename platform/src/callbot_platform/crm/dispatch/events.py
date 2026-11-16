"""Dispatch event emission (same-transaction, tenant-scoped polling feed)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.dispatch import DispatchEvent


def emit_dispatch_event(
    session: Session,
    *,
    tenant_id: UUID,
    event_type: str,
    payload: dict[str, Any],
) -> DispatchEvent:
    row = DispatchEvent(
        tenant_id=tenant_id,
        event_type=event_type,
        payload=payload,
    )
    session.add(row)
    session.flush()
    return row


def list_events_after(
    session: Session,
    tenant_id: UUID,
    *,
    after_id: UUID | None = None,
    limit: int = 100,
) -> list[dict[str, Any]]:
    q = (
        select(DispatchEvent)
        .where(DispatchEvent.tenant_id == tenant_id)
        .order_by(DispatchEvent.created_at.asc(), DispatchEvent.id.asc())
        .limit(min(max(limit, 1), 500))
    )
    if after_id is not None:
        anchor = session.scalar(
            select(DispatchEvent).where(
                DispatchEvent.id == after_id,
                DispatchEvent.tenant_id == tenant_id,
            )
        )
        if anchor is not None:
            q = q.where(
                (DispatchEvent.created_at > anchor.created_at)
                | (
                    (DispatchEvent.created_at == anchor.created_at)
                    & (DispatchEvent.id > anchor.id)
                )
            )
    rows = list(session.scalars(q).all())
    return [
        {
            "id": str(r.id),
            "event_type": r.event_type,
            "payload": r.payload or {},
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
