"""SMS channel handoff — pause AI, assign human, attach context to thread."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.db.models.sms import SmsConversation
from callbot_platform.human_handoff.errors import HandoffDomainError
from callbot_platform.human_handoff.service import HumanHandoffService


class SmsHandoffService:
    """SMS-specific facade: create handoff + mark conversation HANDOFF (AI paused)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self._inner = HumanHandoffService(session)

    def request(
        self,
        *,
        tenant_id: UUID,
        actor: str,
        reason: str | None = None,
        summary: str | None = None,
        department: str | None = None,
        emergency: bool = False,
        conversation_id: UUID | None = None,
        customer_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        result = self._inner.create_request(
            tenant_id=tenant_id,
            channel="SMS",
            actor=actor,
            reason=reason,
            summary=summary,
            department=department,
            emergency=emergency,
            conversation_id=conversation_id,
            customer_id=customer_id,
            idempotency_key=idempotency_key,
        )
        if conversation_id is not None:
            self.pause_ai(tenant_id, conversation_id)
        return result

    def pause_ai(self, tenant_id: UUID, conversation_id: UUID) -> None:
        row = self._session.get(SmsConversation, conversation_id)
        if row is None or row.tenant_id != tenant_id:
            raise HandoffDomainError(
                "conversation_not_found", "SMS conversation not found"
            )
        row.status = "HANDOFF"
        self._session.flush()
