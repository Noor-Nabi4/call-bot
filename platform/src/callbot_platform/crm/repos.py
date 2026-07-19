"""Tenant-scoped CRM repositories. Every query requires tenant_id."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.db.models import (
    Call,
    Customer,
    CustomerPhone,
    Lead,
    TenantAgentSettings,
)
from callbot_platform.domain.phone import PhoneNumberError, normalize_e164
from callbot_platform.telephony.audit import write_audit


class CrmError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


def _ref_code() -> str:
    return f"JB-{secrets.token_hex(3).upper()}"


class CustomerRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def lookup_by_phone(self, tenant_id: UUID, phone: str) -> dict[str, Any] | None:
        e164 = normalize_e164(phone)
        row = self._session.scalar(
            select(CustomerPhone)
            .where(
                CustomerPhone.tenant_id == tenant_id,
                CustomerPhone.e164 == e164,
            )
            .options(selectinload(CustomerPhone.customer).selectinload(Customer.phones))
        )
        if row is None:
            return None
        return self._serialize_customer(row.customer)

    def upsert(
        self,
        tenant_id: UUID,
        *,
        name: str,
        phone: str,
        email: str | None = None,
        address: str | None = None,
        actor: str = "voice-agent",
    ) -> dict[str, Any]:
        if not name or not name.strip():
            raise CrmError("invalid_name", "Customer name is required")
        e164 = normalize_e164(phone)
        existing_phone = self._session.scalar(
            select(CustomerPhone).where(
                CustomerPhone.tenant_id == tenant_id,
                CustomerPhone.e164 == e164,
            )
        )
        if existing_phone is not None:
            customer = self._session.get(Customer, existing_phone.customer_id)
            if customer is None or customer.tenant_id != tenant_id:
                raise CrmError("not_found", "Customer not found for tenant")
            customer.name = name.strip()
            if email is not None:
                customer.email = email.strip() or None
            if address is not None:
                customer.address = address.strip() or None
            customer.updated_at = datetime.now(UTC)
            created = False
        else:
            customer = Customer(
                tenant_id=tenant_id,
                name=name.strip(),
                email=(email.strip() if email else None) or None,
                address=(address.strip() if address else None) or None,
            )
            self._session.add(customer)
            self._session.flush()
            self._session.add(
                CustomerPhone(
                    tenant_id=tenant_id, customer_id=customer.id, e164=e164
                )
            )
            created = True

        self._session.flush()
        self._session.refresh(customer, attribute_names=["phones"])
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="customer_created" if created else "customer_updated",
            resource_ids={"customer_id": str(customer.id), "e164": e164},
        )
        return self._serialize_customer(customer)

    def get(self, tenant_id: UUID, customer_id: UUID) -> dict[str, Any] | None:
        customer = self._session.scalar(
            select(Customer)
            .where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
            .options(selectinload(Customer.phones))
        )
        if customer is None:
            return None
        return self._serialize_customer(customer)

    def _serialize_customer(self, customer: Customer) -> dict[str, Any]:
        phones = [p.e164 for p in (customer.phones or [])]
        return {
            "id": str(customer.id),
            "tenant_id": str(customer.tenant_id),
            "name": customer.name,
            "email": customer.email,
            "address": customer.address,
            "phones": phones,
            "created_at": customer.created_at.isoformat() if customer.created_at else None,
            "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
        }


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
            reference_code=_ref_code(),
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


class AgentSettingsRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, tenant_id: UUID) -> dict[str, Any] | None:
        row = self._session.scalar(
            select(TenantAgentSettings).where(
                TenantAgentSettings.tenant_id == tenant_id
            )
        )
        if row is None:
            return None
        return self._serialize(row)

    def upsert(
        self,
        tenant_id: UUID,
        *,
        business_prompt_facts: dict[str, Any] | None = None,
        voice: str | None = None,
        language: str | None = None,
        greeting: str | None = None,
        actor: str = "tenant_user",
    ) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantAgentSettings).where(
                TenantAgentSettings.tenant_id == tenant_id
            )
        )
        if row is None:
            row = TenantAgentSettings(
                tenant_id=tenant_id,
                business_prompt_facts=business_prompt_facts or {},
                voice=voice or "marin",
                language=language or "en",
                greeting=greeting,
            )
            self._session.add(row)
        else:
            if business_prompt_facts is not None:
                row.business_prompt_facts = business_prompt_facts
            if voice is not None:
                row.voice = voice
            if language is not None:
                row.language = language
            if greeting is not None:
                row.greeting = greeting
            row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="agent_settings_upserted",
            resource_ids={"tenant_id": str(tenant_id)},
        )
        return self._serialize(row)

    def _serialize(self, row: TenantAgentSettings) -> dict[str, Any]:
        return {
            "tenant_id": str(row.tenant_id),
            "business_prompt_facts": row.business_prompt_facts,
            "voice": row.voice,
            "language": row.language,
            "greeting": row.greeting,
        }
