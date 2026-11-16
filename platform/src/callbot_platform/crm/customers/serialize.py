"""Customer serialization helpers."""

from __future__ import annotations

from typing import Any

from callbot_platform.db.models import (
    Customer,
    CustomerLocation,
    CustomerNote,
    CustomerTag,
)


def serialize_customer(
    customer: Customer,
    *,
    include_locations: bool = False,
    include_tags: bool = True,
    include_notes: bool = False,
) -> dict[str, Any]:
    phones = [p.e164 for p in (customer.phones or [])]
    tags: list[dict[str, str]] = []
    if include_tags:
        for link in customer.tag_links or []:
            tag = link.tag
            if tag is None:
                continue
            tags.append({"id": str(tag.id), "name": tag.name})
    payload: dict[str, Any] = {
        "id": str(customer.id),
        "tenant_id": str(customer.tenant_id),
        "name": customer.name,
        "display_name": customer.name,
        "first_name": customer.first_name,
        "last_name": customer.last_name,
        "email": customer.email,
        "email_normalized": customer.email_normalized,
        "address": customer.address,
        "status": customer.status,
        "notes": customer.notes,
        "phones": phones,
        "tags": tags,
        "archived_at": customer.archived_at.isoformat()
        if customer.archived_at
        else None,
        "created_by": customer.created_by,
        "updated_by": customer.updated_by,
        "created_at": customer.created_at.isoformat() if customer.created_at else None,
        "updated_at": customer.updated_at.isoformat() if customer.updated_at else None,
    }
    if include_locations:
        payload["locations"] = [
            serialize_location(loc)
            for loc in (customer.locations or [])
            if loc.archived_at is None
        ]
    if include_notes:
        payload["note_entries"] = [
            serialize_note(n) for n in (customer.customer_notes or [])
        ]
    return payload


def serialize_location(loc: CustomerLocation) -> dict[str, Any]:
    return {
        "id": str(loc.id),
        "tenant_id": str(loc.tenant_id),
        "customer_id": str(loc.customer_id),
        "label": loc.label,
        "address_line_1": loc.address_line_1,
        "address_line_2": loc.address_line_2,
        "city": loc.city,
        "state": loc.state,
        "postal_code": loc.postal_code,
        "country": loc.country,
        "latitude": float(loc.latitude) if loc.latitude is not None else None,
        "longitude": float(loc.longitude) if loc.longitude is not None else None,
        "access_instructions": loc.access_instructions,
        "is_primary": bool(loc.is_primary),
        "archived_at": loc.archived_at.isoformat() if loc.archived_at else None,
        "created_at": loc.created_at.isoformat() if loc.created_at else None,
        "updated_at": loc.updated_at.isoformat() if loc.updated_at else None,
    }


def serialize_note(note: CustomerNote) -> dict[str, Any]:
    return {
        "id": str(note.id),
        "tenant_id": str(note.tenant_id),
        "customer_id": str(note.customer_id),
        "author_user_id": str(note.author_user_id) if note.author_user_id else None,
        "body": note.body,
        "created_at": note.created_at.isoformat() if note.created_at else None,
    }


def serialize_tag(tag: CustomerTag) -> dict[str, Any]:
    return {
        "id": str(tag.id),
        "tenant_id": str(tag.tenant_id),
        "name": tag.name,
        "created_at": tag.created_at.isoformat() if tag.created_at else None,
    }
