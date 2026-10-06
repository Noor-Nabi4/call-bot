"""Lead CRM facade (Phase 8)."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from callbot_platform.crm.errors import CrmError, ref_code
from callbot_platform.crm.leads.activities import LeadActivityService
from callbot_platform.crm.leads.constants import (
    DEFAULT_LEAD_PRIORITY,
    DEFAULT_LEAD_SOURCE,
    DEFAULT_LEAD_STATUS,
    LeadActivityType,
    LeadSource,
)
from callbot_platform.crm.leads.conversion import LeadConversionService
from callbot_platform.crm.leads.cursors import LeadCursor, parse_lead_page
from callbot_platform.crm.leads.normalize import (
    normalize_description,
    normalize_priority,
    normalize_prospect_email,
    normalize_prospect_name,
    normalize_prospect_phone,
    normalize_source,
    normalize_status,
    priority_from_urgency,
    require_title,
)
from callbot_platform.crm.leads.notes import LeadNotesService
from callbot_platform.crm.leads.search import LeadSearchService
from callbot_platform.crm.leads.serialize import (
    serialize_activity,
    serialize_lead,
)
from callbot_platform.crm.leads.transitions import LeadTransitionService
from callbot_platform.db.models import Call, Customer, Lead, LeadActivity
from callbot_platform.db.models.catalog.product import Product
from callbot_platform.db.models.jobs import TenantUser
from callbot_platform.db.models.services.service import Service
from callbot_platform.organization.membership import MEMBERSHIP_ACTIVE
from callbot_platform.telephony.audit import write_audit


class LeadService:
    """Application service for Lead CRM (RBAC enforced at the route layer)."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.search = LeadSearchService(session)
        self.transitions = LeadTransitionService(session)
        self.notes = LeadNotesService(session)
        self.conversion = LeadConversionService(session)
        self._activities = LeadActivityService(session)

    # --- lookups ---

    def _load(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        *,
        for_update: bool = False,
        require_active: bool = False,
    ) -> Lead:
        q = select(Lead).where(Lead.id == lead_id, Lead.tenant_id == tenant_id)
        if for_update:
            q = q.with_for_update()
        q = q.options(
            selectinload(Lead.customer),
            selectinload(Lead.conversion),
        )
        lead = self._session.scalar(q)
        if lead is None:
            raise CrmError("not_found", "Lead not found for tenant")
        if require_active and lead.archived_at is not None:
            raise CrmError("lead_archived", "Lead is archived")
        return lead

    def _require_customer(
        self, tenant_id: UUID, customer_id: UUID | None
    ) -> Customer | None:
        if customer_id is None:
            return None
        row = self._session.scalar(
            select(Customer).where(
                Customer.id == customer_id, Customer.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("customer_not_found", "Customer not found for tenant")
        return row

    def _require_service(
        self, tenant_id: UUID, service_id: UUID | None
    ) -> Service | None:
        if service_id is None:
            return None
        row = self._session.scalar(
            select(Service).where(
                Service.id == service_id, Service.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("service_not_found", "Service not found for tenant")
        return row

    def _require_product(
        self, tenant_id: UUID, product_id: UUID | None
    ) -> Product | None:
        if product_id is None:
            return None
        row = self._session.scalar(
            select(Product).where(
                Product.id == product_id, Product.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("product_not_found", "Product not found for tenant")
        return row

    def _require_owner(
        self, tenant_id: UUID, owner_user_id: UUID | None
    ) -> TenantUser | None:
        if owner_user_id is None:
            return None
        row = self._session.scalar(
            select(TenantUser).where(
                TenantUser.id == owner_user_id, TenantUser.tenant_id == tenant_id
            )
        )
        if row is None:
            raise CrmError("owner_not_found", "Owner not found for tenant")
        if not row.is_active or row.status != MEMBERSHIP_ACTIVE:
            raise CrmError(
                "owner_inactive", "Owner must be an active organization member"
            )
        return row

    def _hydrate(self, lead: Lead) -> dict[str, Any]:
        service = (
            self._session.scalar(
                select(Service).where(
                    Service.id == lead.service_id, Service.tenant_id == lead.tenant_id
                )
            )
            if lead.service_id
            else None
        )
        product = (
            self._session.scalar(
                select(Product).where(
                    Product.id == lead.product_id, Product.tenant_id == lead.tenant_id
                )
            )
            if lead.product_id
            else None
        )
        owner = (
            self._session.scalar(
                select(TenantUser).where(
                    TenantUser.id == lead.owner_user_id,
                    TenantUser.tenant_id == lead.tenant_id,
                )
            )
            if lead.owner_user_id
            else None
        )
        return serialize_lead(lead, service=service, product=product, owner=owner)

    # --- CRUD ---

    def get(self, tenant_id: UUID, lead_id: UUID) -> dict[str, Any]:
        lead = self._load(tenant_id, lead_id)
        return self._hydrate(lead)

    def list(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.search.search(tenant_id, **kwargs)

    def pipeline_counts(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.search.pipeline_counts(tenant_id, **kwargs)

    def create(
        self,
        tenant_id: UUID,
        *,
        title: str,
        actor: str,
        actor_user_id: UUID | None = None,
        description: str | None = None,
        source: str | None = None,
        priority: str | None = None,
        status: str | None = None,
        customer_id: UUID | None = None,
        service_id: UUID | None = None,
        product_id: UUID | None = None,
        owner_user_id: UUID | None = None,
        prospect_name: str | None = None,
        prospect_phone: str | None = None,
        prospect_email: str | None = None,
        notes: str | None = None,
        preferred_time_window: str | None = None,
        call_id: UUID | None = None,
        idempotency_key: str | None = None,
        service_type: str | None = None,
        urgency: str | None = None,
    ) -> dict[str, Any]:
        if status is not None and normalize_status(status) != DEFAULT_LEAD_STATUS:
            raise CrmError(
                "invalid_status",
                "New leads must start in NEW; use transition to change status",
            )

        if idempotency_key:
            existing = self._session.scalar(
                select(Lead).where(
                    Lead.tenant_id == tenant_id,
                    Lead.idempotency_key == idempotency_key,
                )
            )
            if existing is not None:
                return self._hydrate(existing)

        title_clean = require_title(title)
        customer = self._require_customer(tenant_id, customer_id)
        service = self._require_service(tenant_id, service_id)
        product = self._require_product(tenant_id, product_id)
        owner = self._require_owner(tenant_id, owner_user_id)

        if call_id is not None:
            call = self._session.scalar(
                select(Call).where(Call.id == call_id, Call.tenant_id == tenant_id)
            )
            if call is None:
                raise CrmError("call_not_found", "Call not found for tenant")

        src = normalize_source(source, default=DEFAULT_LEAD_SOURCE)
        if urgency and not priority:
            prio = priority_from_urgency(urgency)
        else:
            prio = normalize_priority(priority, default=DEFAULT_LEAD_PRIORITY)

        svc_type = (service_type or title_clean)[:128]
        if service is not None and not service_type:
            svc_type = service.name[:128]

        lead = Lead(
            tenant_id=tenant_id,
            customer_id=customer.id if customer else None,
            call_id=call_id,
            title=title_clean,
            description=normalize_description(description),
            source=src,
            priority=prio,
            status=DEFAULT_LEAD_STATUS,
            service_id=service.id if service else None,
            product_id=product.id if product else None,
            owner_user_id=owner.id if owner else None,
            prospect_name=normalize_prospect_name(prospect_name),
            prospect_phone=normalize_prospect_phone(prospect_phone),
            prospect_email=normalize_prospect_email(prospect_email),
            service_type=svc_type,
            urgency=(urgency or "normal").strip().lower()[:32],
            notes=notes.strip() if notes else None,
            preferred_time_window=(
                preferred_time_window.strip() if preferred_time_window else None
            ),
            idempotency_key=idempotency_key,
            reference_code=ref_code(),
            created_by=actor,
            updated_by=actor,
        )
        self._session.add(lead)
        self._session.flush()

        self._activities.record(
            tenant_id,
            lead.id,
            activity_type=LeadActivityType.CREATED.value,
            actor=actor,
            actor_user_id=actor_user_id,
            metadata={"source": src, "status": DEFAULT_LEAD_STATUS},
        )
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="lead_created",
            resource_ids={
                "lead_id": str(lead.id),
                "customer_id": str(lead.customer_id) if lead.customer_id else None,
                "reference_code": lead.reference_code,
            },
            idempotency_key=idempotency_key,
        )
        return self._hydrate(lead)

    def update(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        *,
        actor: str,
        actor_user_id: UUID | None = None,
        title: str | None = None,
        description: str | None = None,
        clear_description: bool = False,
        source: str | None = None,
        priority: str | None = None,
        customer_id: UUID | None = None,
        clear_customer: bool = False,
        service_id: UUID | None = None,
        clear_service: bool = False,
        product_id: UUID | None = None,
        clear_product: bool = False,
        owner_user_id: UUID | None = None,
        clear_owner: bool = False,
        prospect_name: str | None = None,
        prospect_phone: str | None = None,
        prospect_email: str | None = None,
        notes: str | None = None,
        preferred_time_window: str | None = None,
        status: str | None = None,
    ) -> dict[str, Any]:
        if status is not None:
            raise CrmError(
                "use_transition",
                "Status changes must use POST /leads/{id}/transition",
            )

        lead = self._load(tenant_id, lead_id, for_update=True, require_active=True)
        changed: dict[str, Any] = {}

        if title is not None:
            lead.title = require_title(title)
            lead.service_type = lead.title[:128]
            changed["title"] = lead.title
        if description is not None:
            lead.description = normalize_description(description)
            changed["description"] = True
        if clear_description:
            lead.description = None
            changed["description"] = None
        if source is not None:
            lead.source = normalize_source(source)
            changed["source"] = lead.source
        if priority is not None:
            lead.priority = normalize_priority(priority)
            changed["priority"] = lead.priority

        if clear_customer:
            lead.customer_id = None
            changed["customer_id"] = None
        elif customer_id is not None:
            cust = self._require_customer(tenant_id, customer_id)
            assert cust is not None
            if lead.customer_id != cust.id:
                lead.customer_id = cust.id
                changed["customer_id"] = str(cust.id)
                self._activities.record(
                    tenant_id,
                    lead_id,
                    activity_type=LeadActivityType.CUSTOMER_LINKED.value,
                    actor=actor,
                    actor_user_id=actor_user_id,
                    metadata={"customer_id": str(cust.id)},
                )

        if clear_service:
            lead.service_id = None
            changed["service_id"] = None
        elif service_id is not None:
            svc = self._require_service(tenant_id, service_id)
            assert svc is not None
            if lead.service_id != svc.id:
                lead.service_id = svc.id
                changed["service_id"] = str(svc.id)
                self._activities.record(
                    tenant_id,
                    lead_id,
                    activity_type=LeadActivityType.SERVICE_LINKED.value,
                    actor=actor,
                    actor_user_id=actor_user_id,
                    metadata={"service_id": str(svc.id)},
                )

        if clear_product:
            lead.product_id = None
            changed["product_id"] = None
        elif product_id is not None:
            prod = self._require_product(tenant_id, product_id)
            assert prod is not None
            if lead.product_id != prod.id:
                lead.product_id = prod.id
                changed["product_id"] = str(prod.id)
                self._activities.record(
                    tenant_id,
                    lead_id,
                    activity_type=LeadActivityType.PRODUCT_LINKED.value,
                    actor=actor,
                    actor_user_id=actor_user_id,
                    metadata={"product_id": str(prod.id)},
                )

        if clear_owner:
            prev = lead.owner_user_id
            lead.owner_user_id = None
            if prev is not None:
                changed["owner_user_id"] = None
                self._activities.record(
                    tenant_id,
                    lead_id,
                    activity_type=LeadActivityType.OWNER_CHANGED.value,
                    actor=actor,
                    actor_user_id=actor_user_id,
                    metadata={"from": str(prev), "to": None},
                )
                write_audit(
                    self._session,
                    tenant_id=tenant_id,
                    actor=actor,
                    action="lead_owner_changed",
                    resource_ids={
                        "lead_id": str(lead_id),
                        "from": str(prev),
                        "to": None,
                    },
                )
        elif owner_user_id is not None:
            owner = self._require_owner(tenant_id, owner_user_id)
            assert owner is not None
            if lead.owner_user_id != owner.id:
                prev = lead.owner_user_id
                lead.owner_user_id = owner.id
                changed["owner_user_id"] = str(owner.id)
                self._activities.record(
                    tenant_id,
                    lead_id,
                    activity_type=LeadActivityType.OWNER_CHANGED.value,
                    actor=actor,
                    actor_user_id=actor_user_id,
                    metadata={
                        "from": str(prev) if prev else None,
                        "to": str(owner.id),
                    },
                )
                write_audit(
                    self._session,
                    tenant_id=tenant_id,
                    actor=actor,
                    action="lead_owner_changed",
                    resource_ids={
                        "lead_id": str(lead_id),
                        "from": str(prev) if prev else None,
                        "to": str(owner.id),
                    },
                )

        if prospect_name is not None:
            lead.prospect_name = normalize_prospect_name(prospect_name)
        if prospect_phone is not None:
            lead.prospect_phone = normalize_prospect_phone(prospect_phone)
        if prospect_email is not None:
            lead.prospect_email = normalize_prospect_email(prospect_email)
        if notes is not None:
            lead.notes = notes.strip() or None
        if preferred_time_window is not None:
            lead.preferred_time_window = preferred_time_window.strip() or None

        lead.updated_by = actor
        lead.updated_at = datetime.now(UTC)
        self._session.flush()

        if changed:
            self._activities.record(
                tenant_id,
                lead_id,
                activity_type=LeadActivityType.UPDATED.value,
                actor=actor,
                actor_user_id=actor_user_id,
                metadata={"fields": sorted(changed.keys())},
            )
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="lead_updated",
                resource_ids={"lead_id": str(lead_id), "fields": list(changed.keys())},
            )
        return self._hydrate(lead)

    def archive(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        *,
        actor: str,
        actor_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        lead = self._load(tenant_id, lead_id, for_update=True)
        if lead.archived_at is None:
            lead.archived_at = datetime.now(UTC)
            lead.updated_by = actor
            self._session.flush()
            self._activities.record(
                tenant_id,
                lead_id,
                activity_type=LeadActivityType.ARCHIVED.value,
                actor=actor,
                actor_user_id=actor_user_id,
            )
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="lead_archived",
                resource_ids={"lead_id": str(lead_id)},
            )
        return self._hydrate(lead)

    def restore(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        *,
        actor: str,
        actor_user_id: UUID | None = None,
    ) -> dict[str, Any]:
        lead = self._load(tenant_id, lead_id, for_update=True)
        if lead.archived_at is not None:
            lead.archived_at = None
            lead.updated_by = actor
            self._session.flush()
            self._activities.record(
                tenant_id,
                lead_id,
                activity_type=LeadActivityType.RESTORED.value,
                actor=actor,
                actor_user_id=actor_user_id,
            )
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor=actor,
                action="lead_restored",
                resource_ids={"lead_id": str(lead_id)},
            )
        return self._hydrate(lead)

    def transition_status(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        *,
        to_status: str,
        actor: str,
        actor_user_id: UUID | None = None,
        reason: str | None = None,
    ) -> dict[str, Any]:
        return self.transitions.transition(
            tenant_id,
            lead_id,
            to_status=to_status,
            actor=actor,
            actor_user_id=actor_user_id,
            reason=reason,
        )

    def convert(self, tenant_id: UUID, lead_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.conversion.convert(tenant_id, lead_id, **kwargs)

    def list_activities(
        self,
        tenant_id: UUID,
        lead_id: UUID,
        *,
        limit: int | None = 50,
        cursor: str | None = None,
    ) -> dict[str, Any]:
        self._load(tenant_id, lead_id)
        try:
            page, decoded = parse_lead_page(limit=limit, cursor=cursor)
        except ValueError as exc:
            raise CrmError("invalid_cursor", "Invalid pagination cursor") from exc

        q = select(LeadActivity).where(
            LeadActivity.tenant_id == tenant_id, LeadActivity.lead_id == lead_id
        )
        if decoded is not None:
            q = q.where(
                (LeadActivity.created_at < decoded.created_at)
                | (
                    (LeadActivity.created_at == decoded.created_at)
                    & (LeadActivity.id < decoded.id)
                )
            )
        q = q.order_by(LeadActivity.created_at.desc(), LeadActivity.id.desc()).limit(
            page.limit + 1
        )
        rows = list(self._session.scalars(q).all())
        next_cursor = None
        if len(rows) > page.limit:
            rows = rows[: page.limit]
            last = rows[-1]
            next_cursor = LeadCursor(created_at=last.created_at, id=last.id).encode()
        return {
            "activities": [serialize_activity(r) for r in rows],
            "next_cursor": next_cursor,
            "limit": page.limit,
        }


# Voice-path helper used by LeadRepository
def voice_create_defaults(
    *,
    service_type: str,
    urgency: str,
    call_id: UUID | None,
) -> dict[str, Any]:
    return {
        "title": service_type.strip()[:255],
        "source": LeadSource.AI_AGENT.value if call_id else DEFAULT_LEAD_SOURCE,
        "priority": priority_from_urgency(urgency),
        "status": DEFAULT_LEAD_STATUS,
        "service_type": service_type.strip()[:128],
        "urgency": (urgency or "normal").strip().lower(),
    }
