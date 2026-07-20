"""Lead repository."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError, ref_code
from callbot_platform.db.models import Call, Customer, Lead
from callbot_platform.telephony.audit import write_audit


class LeadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        tenant_id: UUID,
        *,
        customer_id: UUID,
        service_type: str,
        urgency: str = "normal",
        notes: str | None = None,
        preferred_time_window: str | None = None,
        call_id: UUID | None = None,
        idempotency_key: str | None = None,
        actor: str = "voice-agent",
    ) -> dict[str, Any]:
        if not service_type or not service_type.strip():
            raise CrmError("invalid_service_type", "service_type is required")

        customer = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        )
        if customer is None:
            raise CrmError("customer_not_found", "Customer not found for tenant")

        if idempotency_key:
            existing = self._session.scalar(
                select(Lead).where(
                    Lead.tenant_id == tenant_id,
                    Lead.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return self._serialize(existing)

        if call_id is not None:
            call = self._session.scalar(
                select(Call).where(Call.id == call_id, Call.tenant_id == tenant_id)
            )
            if call is None:
                raise CrmError("call_not_found", "Call not found for tenant")

        lead = Lead(
            tenant_id=tenant_id,
            customer_id=customer_id,
            call_id=call_id,
            service_type=service_type.strip(),
            urgency=(urgency or "normal").strip().lower(),
            notes=notes.strip() if notes else None,
            preferred_time_window=(
                preferred_time_window.strip() if preferred_time_window else None
            ),
            status="new",
            idempotency_key=idempotency_key,
            reference_code=ref_code(),
        )
        self._session.add(lead)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="lead_created",
            resource_ids={
                "lead_id": str(lead.id),
                "customer_id": str(customer_id),
                "reference_code": lead.reference_code,
            },
            idempotency_key=idempotency_key,
        )
        return self._serialize(lead)

    def get(self, tenant_id: UUID, lead_id: UUID) -> dict[str, Any] | None:
        lead = self._session.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
        )
        if lead is None:
            return None
        return self._serialize(lead)

    def _serialize(self, lead: Lead) -> dict[str, Any]:
        return {
            "id": str(lead.id),
            "tenant_id": str(lead.tenant_id),
            "customer_id": str(lead.customer_id),
            "call_id": str(lead.call_id) if lead.call_id else None,
            "service_type": lead.service_type,
            "urgency": lead.urgency,
            "notes": lead.notes,
            "preferred_time_window": lead.preferred_time_window,
            "status": lead.status,
            "idempotency_key": lead.idempotency_key,
            "reference_code": lead.reference_code,
            "created_at": lead.created_at.isoformat() if lead.created_at else None,
        }
