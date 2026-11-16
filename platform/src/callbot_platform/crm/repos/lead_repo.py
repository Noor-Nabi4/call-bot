"""Lead repository (voice / internal create + get)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError, ref_code
from callbot_platform.crm.leads.activities import LeadActivityService
from callbot_platform.crm.leads.constants import (
    DEFAULT_LEAD_STATUS,
    LeadActivityType,
    LeadSource,
)
from callbot_platform.crm.leads.normalize import (
    normalize_prospect_email,
    normalize_prospect_name,
    normalize_prospect_phone,
    priority_from_urgency,
)
from callbot_platform.crm.leads.serialize import serialize_lead
from callbot_platform.db.models import Call, Customer, Lead
from callbot_platform.telephony.audit import write_audit


class LeadRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create(
        self,
        tenant_id: UUID,
        *,
        service_type: str,
        customer_id: UUID | None = None,
        urgency: str = "normal",
        notes: str | None = None,
        preferred_time_window: str | None = None,
        call_id: UUID | None = None,
        idempotency_key: str | None = None,
        actor: str = "voice-agent",
        prospect_name: str | None = None,
        prospect_phone: str | None = None,
        prospect_email: str | None = None,
    ) -> dict[str, Any]:
        if not service_type or not service_type.strip():
            raise CrmError("invalid_service_type", "service_type is required")

        resolved_customer_id: UUID | None = None
        if customer_id is not None:
            customer = self._session.scalar(
                select(Customer).where(
                    Customer.id == customer_id, Customer.tenant_id == tenant_id
                )
            )
            if customer is None:
                raise CrmError("customer_not_found", "Customer not found for tenant")
            resolved_customer_id = customer.id

        if idempotency_key:
            existing = self._session.scalar(
                select(Lead).where(
                    Lead.tenant_id == tenant_id,
                    Lead.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return serialize_lead(existing)

        if call_id is not None:
            call = self._session.scalar(
                select(Call).where(Call.id == call_id, Call.tenant_id == tenant_id)
            )
            if call is None:
                raise CrmError("call_not_found", "Call not found for tenant")

        title = service_type.strip()[:255]
        lead = Lead(
            tenant_id=tenant_id,
            customer_id=resolved_customer_id,
            call_id=call_id,
            title=title,
            service_type=service_type.strip()[:128],
            urgency=(urgency or "normal").strip().lower()[:32],
            priority=priority_from_urgency(urgency),
            source=LeadSource.AI_AGENT.value if call_id else LeadSource.PHONE.value,
            status=DEFAULT_LEAD_STATUS,
            notes=notes.strip() if notes else None,
            preferred_time_window=(
                preferred_time_window.strip() if preferred_time_window else None
            ),
            prospect_name=normalize_prospect_name(prospect_name),
            prospect_phone=normalize_prospect_phone(prospect_phone),
            prospect_email=normalize_prospect_email(prospect_email),
            idempotency_key=idempotency_key,
            reference_code=ref_code(),
            created_by=actor,
            updated_by=actor,
        )
        self._session.add(lead)
        self._session.flush()
        LeadActivityService(self._session).record(
            tenant_id,
            lead.id,
            activity_type=LeadActivityType.CREATED.value,
            actor=actor,
            metadata={"source": lead.source, "via": "voice"},
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="lead_created",
            resource_ids={
                "lead_id": str(lead.id),
                "customer_id": (
                    str(resolved_customer_id) if resolved_customer_id else None
                ),
                "reference_code": lead.reference_code,
            },
            idempotency_key=idempotency_key,
        )
        return serialize_lead(lead)

    def get(self, tenant_id: UUID, lead_id: UUID) -> dict[str, Any] | None:
        lead = self._session.scalar(
            select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
        )
        if lead is None:
            return None
        return serialize_lead(lead)
