"""Call repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import Call, Customer
from callbot_platform.domain.phone import PhoneNumberError, normalize_e164
from callbot_platform.telephony.audit import write_audit


class CallRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def start(
        self,
        tenant_id: UUID,
        *,
        room_name: str,
        job_id: str | None = None,
        customer_id: UUID | None = None,
        caller_number: str | None = None,
        called_number: str | None = None,
        telephony_provider: str | None = None,
        provider_call_id: str | None = None,
        actor: str = "voice-agent",
    ) -> dict[str, Any]:
        if customer_id is not None:
            customer = self._session.scalar(
                select(Customer).where(
                    Customer.id == customer_id, Customer.tenant_id == tenant_id
                )
            )
            if customer is None:
                raise CrmError("customer_not_found", "Customer not found for tenant")

        caller = None
        called = None
        try:
            if caller_number:
                caller = normalize_e164(caller_number)
            if called_number:
                called = normalize_e164(called_number)
        except PhoneNumberError as exc:
            raise CrmError("invalid_phone", str(exc)) from exc

        call = Call(
            tenant_id=tenant_id,
            customer_id=customer_id,
            room_name=room_name,
            job_id=job_id,
            status="active",
            caller_number=caller,
            called_number=called,
            telephony_provider=telephony_provider,
            provider_call_id=provider_call_id,
            metrics={},
        )
        self._session.add(call)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="call_started",
            resource_ids={"call_id": str(call.id), "room_name": room_name},
        )
        return self._serialize(call)

    def end(
        self,
        tenant_id: UUID,
        *,
        call_id: UUID,
        status: str = "closed",
        disconnect_reason: str | None = None,
        metrics: dict[str, Any] | None = None,
        customer_id: UUID | None = None,
        actor: str = "voice-agent",
    ) -> dict[str, Any]:
        call = self._session.scalar(
            select(Call).where(Call.id == call_id, Call.tenant_id == tenant_id)
        )
        if call is None:
            raise CrmError("call_not_found", "Call not found for tenant")
        call.ended_at = datetime.now(UTC)
        call.status = status
        call.disconnect_reason = disconnect_reason
        if metrics is not None:
            call.metrics = metrics
        if customer_id is not None:
            customer = self._session.scalar(
                select(Customer).where(
                    Customer.id == customer_id, Customer.tenant_id == tenant_id
                )
            )
            if customer is None:
                raise CrmError("customer_not_found", "Customer not found for tenant")
            call.customer_id = customer_id
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="call_ended",
            resource_ids={"call_id": str(call.id)},
            payload_summary={"status": status, "disconnect_reason": disconnect_reason},
        )
        return self._serialize(call)

    def _serialize(self, call: Call) -> dict[str, Any]:
        return {
            "id": str(call.id),
            "tenant_id": str(call.tenant_id),
            "customer_id": str(call.customer_id) if call.customer_id else None,
            "room_name": call.room_name,
            "job_id": call.job_id,
            "started_at": call.started_at.isoformat() if call.started_at else None,
            "ended_at": call.ended_at.isoformat() if call.ended_at else None,
            "status": call.status,
            "disconnect_reason": call.disconnect_reason,
            "metrics": call.metrics,
            "caller_number": call.caller_number,
            "called_number": call.called_number,
            "telephony_provider": call.telephony_provider,
            "provider_call_id": call.provider_call_id,
        }
