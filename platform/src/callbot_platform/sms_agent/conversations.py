"""SMS conversation load/create with bounded history."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.db.models.sms import SmsConversation, SmsMessage
from callbot_platform.sms_agent.constants import DEFAULT_CONTEXT_MESSAGES

logger = logging.getLogger(__name__)


class SmsConversationService:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get_or_create(
        self,
        *,
        tenant_id: UUID,
        phone_e164: str,
        business_phone_e164: str,
        customer_id: UUID | None,
    ) -> SmsConversation:
        row = self._session.scalar(
            select(SmsConversation).where(
                SmsConversation.tenant_id == tenant_id,
                SmsConversation.phone_e164 == phone_e164,
                SmsConversation.business_phone_e164 == business_phone_e164,
            )
        )
        if row is not None:
            if customer_id is not None and row.customer_id is None:
                row.customer_id = customer_id
            if row.status == "CLOSED":
                row.status = "ACTIVE"
            return row
        row = SmsConversation(
            tenant_id=tenant_id,
            phone_e164=phone_e164,
            business_phone_e164=business_phone_e164,
            customer_id=customer_id,
            status="ACTIVE",
            workflow_state={},
            last_message_at=datetime.now(UTC),
        )
        self._session.add(row)
        try:
            with self._session.begin_nested():
                self._session.flush()
        except IntegrityError:
            self._session.expire_all()
            raced = self._session.scalar(
                select(SmsConversation).where(
                    SmsConversation.tenant_id == tenant_id,
                    SmsConversation.phone_e164 == phone_e164,
                    SmsConversation.business_phone_e164 == business_phone_e164,
                )
            )
            if raced is None:
                raise
            if customer_id is not None and raced.customer_id is None:
                raced.customer_id = customer_id
            if raced.status == "CLOSED":
                raced.status = "ACTIVE"
            return raced
        return row

    def load_context(
        self,
        *,
        tenant_id: UUID,
        conversation_id: UUID,
        limit: int = DEFAULT_CONTEXT_MESSAGES,
    ) -> list[dict[str, Any]]:
        lim = max(1, min(int(limit), 50))
        rows = self._session.scalars(
            select(SmsMessage)
            .where(
                SmsMessage.tenant_id == tenant_id,
                SmsMessage.conversation_id == conversation_id,
            )
            .order_by(SmsMessage.created_at.desc())
            .limit(lim)
        ).all()
        out: list[dict[str, Any]] = []
        for row in reversed(rows):
            out.append(
                {
                    "direction": row.direction,
                    "body": row.body,
                    "status": row.status,
                    "created_at": row.created_at.isoformat()
                    if row.created_at
                    else None,
                    "intent": row.intent,
                }
            )
        return out

    def update_workflow(
        self, conversation: SmsConversation, patch: dict[str, Any]
    ) -> None:
        state = dict(conversation.workflow_state or {})
        state.update(patch)
        conversation.workflow_state = state
        conversation.updated_at = datetime.now(UTC)
        self._session.flush()

    def clear_workflow_keys(
        self, conversation: SmsConversation, keys: list[str]
    ) -> None:
        state = dict(conversation.workflow_state or {})
        for key in keys:
            state.pop(key, None)
        conversation.workflow_state = state
        self._session.flush()
