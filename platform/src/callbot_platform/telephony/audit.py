"""Audit logging for telephony mutations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.db.models import TelephonyAuditEvent


def write_audit(
    session: Session,
    *,
    tenant_id: UUID | None,
    actor: str,
    action: str,
    resource_ids: dict[str, Any] | None = None,
    request_id: str | None = None,
    idempotency_key: str | None = None,
    payload_summary: dict[str, Any] | None = None,
) -> TelephonyAuditEvent:
    event = TelephonyAuditEvent(
        tenant_id=tenant_id,
        actor=actor,
        action=action,
        resource_ids=resource_ids or {},
        request_id=request_id,
        idempotency_key=idempotency_key,
        payload_summary=payload_summary or {},
    )
    session.add(event)
    session.flush()
    return event
