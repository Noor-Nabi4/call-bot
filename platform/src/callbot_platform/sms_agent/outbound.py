"""Outbound SMS via NotificationOutbox — never AI-selected destinations."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.db.models.sms import SmsConversation, SmsMessage
from callbot_platform.scheduling.notifications import NotificationService
from callbot_platform.sms_agent.constants import MAX_OUTBOUND_CHARS

logger = logging.getLogger(__name__)


class SmsOutboundService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._notifications = NotificationService(session)

    def enqueue_reply(
        self,
        *,
        conversation: SmsConversation,
        body: str,
        idempotency_key: str,
        operation_id: UUID | None = None,
        customer_id: UUID | None = None,
    ) -> dict[str, Any]:
        text = (body or "").strip()
        if not text:
            text = "Sorry — I couldn't complete that. Please try again."
        if len(text) > MAX_OUTBOUND_CHARS:
            text = text[: MAX_OUTBOUND_CHARS - 1].rstrip() + "…"

        # Destination is always the server-resolved conversation phone.
        queued = self._notifications.enqueue_sms(
            tenant_id=conversation.tenant_id,
            to_address=conversation.phone_e164,
            body=text,
            idempotency_key=idempotency_key,
        )
        outbox_id = queued.get("outbox_id") or queued.get("id")
        msg = SmsMessage(
            tenant_id=conversation.tenant_id,
            conversation_id=conversation.id,
            customer_id=customer_id or conversation.customer_id,
            provider_message_id=None,
            direction="OUTBOUND",
            sender_phone=conversation.business_phone_e164,
            recipient_phone=conversation.phone_e164,
            body=text,
            status="QUEUED",
            operation_id=operation_id,
            outbox_id=UUID(str(outbox_id)) if outbox_id else None,
            metadata_json={
                "outbox_status": queued.get("status"),
                "idempotent": bool(queued.get("idempotent")),
            },
        )
        self._session.add(msg)
        conversation.last_message_at = datetime.now(UTC)
        self._session.flush()
        logger.info(
            "sms.outbound.queued tenant_id=%s conversation_id=%s message_id=%s",
            conversation.tenant_id,
            conversation.id,
            msg.id,
        )
        return {
            "message_id": str(msg.id),
            "status": "QUEUED",
            "outbox_id": str(outbox_id) if outbox_id else None,
            "idempotent": bool(queued.get("idempotent")),
        }
