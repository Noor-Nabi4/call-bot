"""Customer repository (voice-era lookup/upsert compatibility layer)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.customers.normalize import normalize_email
from callbot_platform.crm.customers.serialize import serialize_customer
from callbot_platform.crm.customers.status import DEFAULT_CUSTOMER_STATUS
from callbot_platform.crm.errors import CrmError
from callbot_platform.db.models import Customer, CustomerPhone, CustomerTagLink
from callbot_platform.domain.phone import normalize_e164
from callbot_platform.telephony.audit import write_audit


class CustomerRepository:
    """Preserves voice agent lookup/upsert contracts on the extended Customer model."""

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
            .options(
                selectinload(CustomerPhone.customer).selectinload(Customer.phones),
                selectinload(CustomerPhone.customer)
                .selectinload(Customer.tag_links)
                .selectinload(CustomerTagLink.tag),
            )
        )
        if row is None or row.customer is None:
            return None
        if row.customer.tenant_id != tenant_id:
            return None
        return serialize_customer(row.customer)

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
        email_norm = normalize_email(email) if email is not None else None
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
                customer.email = email_norm
                customer.email_normalized = email_norm
            if address is not None:
                customer.address = address.strip() or None
            customer.updated_by = actor
            customer.updated_at = datetime.now(UTC)
            # Voice upsert may restore an archived match by phone.
            if customer.archived_at is not None:
                customer.archived_at = None
            created = False
        else:
            customer = Customer(
                tenant_id=tenant_id,
                name=name.strip(),
                email=email_norm,
                email_normalized=email_norm,
                address=(address.strip() if address else None) or None,
                status=DEFAULT_CUSTOMER_STATUS,
                created_by=actor,
                updated_by=actor,
            )
            self._session.add(customer)
            self._session.flush()
            self._session.add(
                CustomerPhone(tenant_id=tenant_id, customer_id=customer.id, e164=e164)
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
        return serialize_customer(customer)

    def get(self, tenant_id: UUID, customer_id: UUID) -> dict[str, Any] | None:
        customer = self._session.scalar(
            select(Customer)
            .where(Customer.id == customer_id, Customer.tenant_id == tenant_id)
            .options(
                selectinload(Customer.phones),
                selectinload(Customer.tag_links).selectinload(CustomerTagLink.tag),
            )
        )
        if customer is None:
            return None
        return serialize_customer(customer)
