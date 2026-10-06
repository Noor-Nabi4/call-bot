"""Organization repository — tenant is the business entity."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.tenant import Tenant
from callbot_platform.organization.errors import OrganizationError
from callbot_platform.organization.validation import (
    serialize_organization,
    validate_business_type,
    validate_country,
    validate_currency,
    validate_email,
    validate_industry,
    validate_name,
    validate_phone,
    validate_state,
    validate_timezone,
    validate_website,
)
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class OrganizationRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, tenant_id: UUID) -> dict[str, Any]:
        tenant = self._require(tenant_id)
        return serialize_organization(tenant)

    def create(
        self,
        *,
        name: str,
        slug: str,
        timezone: str = "UTC",
        status: str = "active",
        actor: str,
        industry: str | None = None,
        industry_key: str | None = None,
        business_type: str | None = None,
        currency: str | None = None,
        country: str | None = None,
        state: str | None = None,
        website: str | None = None,
        phone: str | None = None,
        email: str | None = None,
    ) -> dict[str, Any]:
        cleaned_slug = slug.strip().lower()
        existing = self._session.scalar(
            select(Tenant).where(Tenant.slug == cleaned_slug)
        )
        if existing is not None:
            raise OrganizationError("slug_taken", "Tenant slug already exists")
        tenant = Tenant(
            name=validate_name(name),
            slug=cleaned_slug,
            timezone=validate_timezone(timezone),
            status=status,
            industry_key=validate_industry(
                industry if industry is not None else industry_key
            ),
            business_type=validate_business_type(business_type),
            currency=validate_currency(currency),
            country=validate_country(country),
            state=validate_state(state),
            website=validate_website(website),
            phone=validate_phone(phone),
            email=validate_email(email),
        )
        self._session.add(tenant)
        self._session.flush()
        from callbot_platform.rbac.seed import ensure_system_roles_for_tenant

        ensure_system_roles_for_tenant(self._session, tenant.id)
        write_audit(
            self._session,
            tenant_id=tenant.id,
            actor=actor,
            action="organization_created",
            resource_ids={"tenant_id": str(tenant.id)},
            payload_summary={"slug": tenant.slug},
        )
        logger.info(
            "organization_created tenant_id=%s slug=%s",
            tenant.id,
            tenant.slug,
        )
        return serialize_organization(tenant)

    def update(
        self,
        tenant_id: UUID,
        *,
        actor: str,
        **fields: Any,
    ) -> dict[str, Any]:
        tenant = self._require(tenant_id)
        if "tenant_id" in fields:
            raise OrganizationError(
                "tenant_override_rejected",
                "tenant_id cannot be changed",
            )
        changed: list[str] = []

        if "name" in fields:
            tenant.name = validate_name(fields["name"])
            changed.append("name")
        if "timezone" in fields:
            tenant.timezone = validate_timezone(fields["timezone"])
            changed.append("timezone")
        if "industry" in fields or "industry_key" in fields:
            raw = fields["industry"] if "industry" in fields else fields["industry_key"]
            tenant.industry_key = validate_industry(raw)
            changed.append("industry")
        if "business_type" in fields:
            tenant.business_type = validate_business_type(fields["business_type"])
            changed.append("business_type")
        if "currency" in fields:
            tenant.currency = validate_currency(fields["currency"])
            changed.append("currency")
        if "country" in fields:
            tenant.country = validate_country(fields["country"])
            changed.append("country")
        if "state" in fields:
            tenant.state = validate_state(fields["state"])
            changed.append("state")
        if "website" in fields:
            tenant.website = validate_website(fields["website"])
            changed.append("website")
        if "phone" in fields:
            tenant.phone = validate_phone(fields["phone"])
            changed.append("phone")
        if "email" in fields:
            tenant.email = validate_email(fields["email"])
            changed.append("email")

        if not changed:
            return serialize_organization(tenant)

        tenant.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant.id,
            actor=actor,
            action="organization_updated",
            resource_ids={"tenant_id": str(tenant.id)},
            payload_summary={"changed_fields": changed},
        )
        logger.info(
            "organization_updated tenant_id=%s actor=%s fields=%s",
            tenant.id,
            actor,
            ",".join(changed),
        )
        return serialize_organization(tenant)

    def _require(self, tenant_id: UUID) -> Tenant:
        tenant = self._session.get(Tenant, tenant_id)
        if tenant is None:
            raise OrganizationError("not_found", "Organization not found")
        return tenant
