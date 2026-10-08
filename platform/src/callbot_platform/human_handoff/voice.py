"""Voice channel handoff — prepares context, routes, notifies, transfers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.human_handoff.service import HumanHandoffService
from callbot_platform.human_handoff.telephony import TelephonyTransferProvider


class VoiceHandoffService:
    """Voice-specific facade over HumanHandoffService (no provider SDKs here)."""

    def __init__(
        self,
        session: Session,
        *,
        transfer_provider: TelephonyTransferProvider | None = None,
    ) -> None:
        self._inner = HumanHandoffService(session, transfer_provider=transfer_provider)

    def request(
        self,
        *,
        tenant_id: UUID,
        actor: str,
        reason: str | None = None,
        summary: str | None = None,
        department: str | None = None,
        emergency: bool = False,
        call_id: UUID | None = None,
        customer_id: UUID | None = None,
        job_id: UUID | None = None,
        appointment_id: UUID | None = None,
        target_user_id: UUID | None = None,
        target_technician_id: UUID | None = None,
        idempotency_key: str | None = None,
    ) -> dict[str, Any]:
        return self._inner.create_request(
            tenant_id=tenant_id,
            channel="VOICE",
            actor=actor,
            reason=reason,
            summary=summary,
            department=department,
            emergency=emergency,
            call_id=call_id,
            customer_id=customer_id,
            job_id=job_id,
            appointment_id=appointment_id,
            target_user_id=target_user_id,
            target_technician_id=target_technician_id,
            idempotency_key=idempotency_key,
        )
