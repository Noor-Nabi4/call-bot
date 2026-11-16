"""Lead serialization helpers."""

from __future__ import annotations

from typing import Any

from callbot_platform.db.models import (
    Customer,
    Lead,
    LeadActivity,
    LeadConversion,
    LeadNote,
)
from callbot_platform.db.models.catalog.product import Product
from callbot_platform.db.models.jobs import TenantUser
from callbot_platform.db.models.services.service import Service


def serialize_lead(
    lead: Lead,
    *,
    customer: Customer | None = None,
    service: Service | None = None,
    product: Product | None = None,
    owner: TenantUser | None = None,
    conversion: LeadConversion | None = None,
) -> dict[str, Any]:
    cust = customer if customer is not None else lead.customer
    svc = service
    prod = product
    own = owner
    conv = conversion if conversion is not None else getattr(lead, "conversion", None)

    return {
        "id": str(lead.id),
        "tenant_id": str(lead.tenant_id),
        "customer_id": str(lead.customer_id) if lead.customer_id else None,
        "customer": (
            {
                "id": str(cust.id),
                "display_name": cust.name,
                "name": cust.name,
                "status": cust.status,
            }
            if cust is not None
            else None
        ),
        "call_id": str(lead.call_id) if lead.call_id else None,
        "title": lead.title or lead.service_type,
        "description": lead.description,
        "source": lead.source,
        "priority": lead.priority,
        "status": lead.status,
        "service_id": str(lead.service_id) if lead.service_id else None,
        "service": (
            {"id": str(svc.id), "name": svc.name, "code": svc.code}
            if svc is not None
            else None
        ),
        "product_id": str(lead.product_id) if lead.product_id else None,
        "product": (
            {"id": str(prod.id), "name": prod.name, "sku": getattr(prod, "sku", None)}
            if prod is not None
            else None
        ),
        "owner_user_id": str(lead.owner_user_id) if lead.owner_user_id else None,
        "owner": (
            {"id": str(own.id), "name": own.name, "email": own.email}
            if own is not None
            else None
        ),
        "prospect_name": lead.prospect_name,
        "prospect_phone": lead.prospect_phone,
        "prospect_email": lead.prospect_email,
        # Legacy voice fields
        "service_type": lead.service_type,
        "urgency": lead.urgency,
        "notes": lead.notes,
        "preferred_time_window": lead.preferred_time_window,
        "idempotency_key": lead.idempotency_key,
        "reference_code": lead.reference_code,
        "archived_at": lead.archived_at.isoformat() if lead.archived_at else None,
        "created_by": lead.created_by,
        "updated_by": lead.updated_by,
        "converted_at": lead.converted_at.isoformat() if lead.converted_at else None,
        "converted_by": lead.converted_by,
        "converted_customer_id": (
            str(lead.converted_customer_id) if lead.converted_customer_id else None
        ),
        "conversion": serialize_conversion(conv) if conv is not None else None,
        "created_at": lead.created_at.isoformat() if lead.created_at else None,
        "updated_at": lead.updated_at.isoformat() if lead.updated_at else None,
    }


def serialize_note(note: LeadNote) -> dict[str, Any]:
    return {
        "id": str(note.id),
        "tenant_id": str(note.tenant_id),
        "lead_id": str(note.lead_id),
        "body": note.body,
        "created_by": note.created_by,
        "updated_by": note.updated_by,
        "archived_at": note.archived_at.isoformat() if note.archived_at else None,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


def serialize_activity(row: LeadActivity) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "lead_id": str(row.lead_id),
        "activity_type": row.activity_type,
        "actor_user_id": str(row.actor_user_id) if row.actor_user_id else None,
        "actor": row.actor,
        "metadata": dict(row.metadata_json or {}),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_conversion(row: LeadConversion) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "lead_id": str(row.lead_id),
        "customer_id": str(row.customer_id),
        "created_customer": bool(row.created_customer),
        "converted_by": row.converted_by,
        "converted_by_user_id": (
            str(row.converted_by_user_id) if row.converted_by_user_id else None
        ),
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
