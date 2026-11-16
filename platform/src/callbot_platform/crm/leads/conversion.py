"""Idempotent Lead → Customer conversion."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.crm.customers.normalize import normalize_email
from callbot_platform.crm.customers.service import CustomerService
from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.leads.activities import LeadActivityService
from callbot_platform.crm.leads.constants import LeadActivityType
from callbot_platform.crm.leads.serialize import serialize_conversion, serialize_lead
from callbot_platform.db.models import Customer, Lead, LeadConversion
from callbot_platform.telephony.audit import write_audit

_CREATE_CUSTOMER_KEYS = frozenset(
    {
        "name",
        "display_name",
        "first_name",
        "last_name",
        "phone",
        "email",
        "address",
        "status",
        "notes",
        "tags",
    }
)


class LeadConversionService:
    def __init__(self, session: Session) -> None:
        self._session = session
        self._activities = LeadActivityService(session)
        self._customers = CustomerService(session)

    def _lookup_by_email(self, tenant_id: UUID, email: str) -> dict[str, Any] | None:
        norm = normalize_email(email)
        if not norm:
            return None
        row = self._session.scalar(
            select(Customer).where(
                Customer.tenant_id == tenant_id,
                Customer.email_normalized == norm,
            )
        )
        if row is None:
            return None
        return {"id": str(row.id)}

    def _sanitize_create(self, payload: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in payload.items() if k in _CREATE_CUSTOMER_KEYS}

    def _resolve_new_customer(
        self,
        tenant_id: UUID,
        lead: Lead,
        *,
        create_customer: dict[str, Any],
        actor: str,
    ) -> tuple[UUID, bool]:
        payload = self._sanitize_create(create_customer)
        # Prefer explicit create payload, then lead prospect fields.
        phone = payload.get("phone") or lead.prospect_phone
        email = payload.get("email") or lead.prospect_email
        if phone and "phone" not in payload:
            payload["phone"] = phone
        if email and "email" not in payload:
            payload["email"] = email
        if not payload.get("name") and not payload.get("display_name"):
            payload["name"] = (lead.prospect_name or lead.title or "Converted lead")[
                :255
            ]

        if phone:
            matched = self._customers.lookup_by_phone(tenant_id, str(phone))
            if matched is not None:
                return UUID(str(matched["id"])), False
        if email:
            matched = self._lookup_by_email(tenant_id, str(email))
            if matched is not None:
                return UUID(str(matched["id"])), False

        created = self._customers.create(tenant_id, actor=actor, **payload)
        return UUID(str(created["id"])), True

    def convert(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        *,
        actor: str,
        actor_user_id: UUID | None = None,
        customer_id: UUID | None = None,
        create_customer: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        lead = self._session.scalar(
            select(Lead)
            .where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
            .with_for_update()
        )
        if lead is None:
            raise CrmError("not_found", "Lead not found for tenant")
        if lead.archived_at is not None:
            raise CrmError("lead_archived", "Cannot convert an archived lead")

        existing = self._session.scalar(
            select(LeadConversion).where(
                LeadConversion.tenant_id == tenant_id,
                LeadConversion.lead_id == lead_id,
            )
        )
        if existing is not None:
            # Idempotent: no duplicate activity/audit on retry.
            return {
                "lead": serialize_lead(lead, conversion=existing),
                "conversion": serialize_conversion(existing),
                "already_converted": True,
            }

        created_customer = False
        target_customer_id: UUID

        if customer_id is not None:
            customer = self._session.scalar(
                select(Customer).where(
                    Customer.id == customer_id, Customer.tenant_id == tenant_id
                )
            )
            if customer is None:
                raise CrmError("customer_not_found", "Customer not found for tenant")
            target_customer_id = customer.id
        elif create_customer is not None:
            target_customer_id, created_customer = self._resolve_new_customer(
                tenant_id, lead, create_customer=create_customer, actor=actor
            )
        elif lead.customer_id is not None:
            target_customer_id = lead.customer_id
        elif lead.prospect_phone or lead.prospect_email or lead.prospect_name:
            target_customer_id, created_customer = self._resolve_new_customer(
                tenant_id,
                lead,
                create_customer={},
                actor=actor,
            )
        else:
            raise CrmError(
                "customer_required",
                "Provide customer_id or create_customer to convert this lead",
            )

        now = datetime.now(UTC)
        conversion = LeadConversion(
            tenant_id=tenant_id,
            lead_id=lead_id,
            customer_id=target_customer_id,
            created_customer=created_customer,
            converted_by=actor,
            converted_by_user_id=actor_user_id,
            created_at=now,
        )
        self._session.add(conversion)

        lead.customer_id = target_customer_id
        lead.converted_at = now
        lead.converted_by = actor
        lead.converted_customer_id = target_customer_id
        lead.updated_by = actor
        lead.updated_at = now

        try:
            with self._session.begin_nested():
                self._session.flush()
        except IntegrityError:
            # Concurrent convert won UNIQUE(tenant_id, lead_id); return winner.
            self._session.expire_all()
            lead2 = self._session.scalar(
                select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
            )
            existing2 = self._session.scalar(
                select(LeadConversion).where(
                    LeadConversion.tenant_id == tenant_id,
                    LeadConversion.lead_id == lead_id,
                )
            )
            if lead2 is None or existing2 is None:
                raise CrmError("convert_conflict", "Conversion conflict") from None
            return {
                "lead": serialize_lead(lead2, conversion=existing2),
                "conversion": serialize_conversion(existing2),
                "already_converted": True,
            }

        self._activities.record(
            tenant_id,
            lead_id,
            activity_type=LeadActivityType.CONVERTED.value,
            actor=actor,
            actor_user_id=actor_user_id,
            metadata={
                "customer_id": str(target_customer_id),
                "created_customer": created_customer,
            },
        )
        self._activities.record(
            tenant_id,
            lead_id,
            activity_type=LeadActivityType.CUSTOMER_LINKED.value,
            actor=actor,
            actor_user_id=actor_user_id,
            metadata={"customer_id": str(target_customer_id)},
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="lead_converted",
            resource_ids={
                "lead_id": str(lead_id),
                "customer_id": str(target_customer_id),
                "created_customer": created_customer,
            },
        )
        return {
            "lead": serialize_lead(lead, conversion=conversion),
            "conversion": serialize_conversion(conversion),
            "already_converted": False,
        }
