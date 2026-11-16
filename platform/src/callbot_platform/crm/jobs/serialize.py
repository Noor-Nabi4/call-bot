"""Job serialization."""

from __future__ import annotations

from typing import Any

from callbot_platform.db.models.jobs import (
    Job,
    JobAttachment,
    JobNote,
    JobStatusHistory,
)


def serialize_note(note: JobNote) -> dict[str, Any]:
    return {
        "id": str(note.id),
        "tenant_id": str(note.tenant_id),
        "job_id": str(note.job_id),
        "body": note.body,
        "author_user_id": str(note.author_user_id) if note.author_user_id else None,
        "author_name": note.author.name if note.author else None,
        "updated_by": note.updated_by,
        "archived_at": note.archived_at.isoformat() if note.archived_at else None,
        "created_at": note.created_at.isoformat() if note.created_at else None,
        "updated_at": note.updated_at.isoformat() if note.updated_at else None,
    }


def serialize_attachment(
    row: JobAttachment, *, download_url: str | None = None
) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "job_id": str(row.job_id),
        "object_key": row.object_key,
        "filename": row.filename,
        "content_type": row.content_type,
        "size_bytes": row.size_bytes,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "archived_at": row.archived_at.isoformat() if row.archived_at else None,
        "download_url": download_url,
    }


def serialize_status_history(row: JobStatusHistory) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "job_id": str(row.job_id),
        "from_status": row.from_status,
        "to_status": row.to_status,
        "changed_by": row.changed_by,
        "reason": row.reason,
        "metadata": row.metadata_json or {},
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_job(
    job: Job,
    *,
    include_notes: bool = False,
    include_history: bool = False,
    include_attachments: bool = False,
    attachment_urls: dict[str, str] | None = None,
) -> dict[str, Any]:
    customer = None
    if job.customer is not None:
        customer = {
            "id": str(job.customer.id),
            "name": job.customer.name,
            "display_name": job.customer.name,
            "email": job.customer.email,
            "status": job.customer.status,
        }
    tech = None
    if job.assigned_technician is not None:
        tech = {
            "id": str(job.assigned_technician.id),
            "display_name": job.assigned_technician.display_name,
        }
    location = None
    if job.location is not None:
        location = {
            "id": str(job.location.id),
            "label": job.location.label,
            "address_line_1": job.location.address_line_1,
            "city": job.location.city,
            "state": job.location.state,
            "postal_code": job.location.postal_code,
        }
    service = None
    if job.service is not None:
        service = {
            "id": str(job.service.id),
            "name": job.service.name,
            "code": getattr(job.service, "code", None),
        }
    payload: dict[str, Any] = {
        "id": str(job.id),
        "tenant_id": str(job.tenant_id),
        "job_number": job.job_number,
        "reference_code": job.reference_code,
        "customer_id": str(job.customer_id),
        "customer": customer,
        "location_id": str(job.location_id) if job.location_id else None,
        "equipment_id": str(job.equipment_id) if job.equipment_id else None,
        "location": location,
        "service_id": str(job.service_id) if job.service_id else None,
        "service": service,
        "service_type": job.service_type,
        "description": job.description,
        "priority": job.priority,
        "status": job.status,
        "assigned_technician_id": (
            str(job.assigned_technician_id) if job.assigned_technician_id else None
        ),
        "assigned_technician": tech,
        "appointment_id": str(job.appointment_id) if job.appointment_id else None,
        "lead_id": str(job.lead_id) if job.lead_id else None,
        "call_id": str(job.call_id) if job.call_id else None,
        "scheduled_starts_at": (
            job.scheduled_starts_at.isoformat() if job.scheduled_starts_at else None
        ),
        "scheduled_ends_at": (
            job.scheduled_ends_at.isoformat() if job.scheduled_ends_at else None
        ),
        "checklist": job.checklist or [],
        "completion_notes": job.completion_notes,
        "idempotency_key": job.idempotency_key,
        "created_by": job.created_by,
        "updated_by": job.updated_by,
        "completed_at": job.completed_at.isoformat() if job.completed_at else None,
        "cancelled_at": job.cancelled_at.isoformat() if job.cancelled_at else None,
        "archived_at": job.archived_at.isoformat() if job.archived_at else None,
        "created_at": job.created_at.isoformat() if job.created_at else None,
        "updated_at": job.updated_at.isoformat() if job.updated_at else None,
    }
    if include_notes:
        notes = [n for n in (job.notes or []) if n.archived_at is None]
        notes.sort(
            key=lambda n: (n.created_at.isoformat() if n.created_at else "", str(n.id))
        )
        payload["notes"] = [serialize_note(n) for n in notes]
    if include_history:
        history = sorted(
            job.status_history or [],
            key=lambda h: (
                h.created_at.isoformat() if h.created_at else "",
                str(h.id),
            ),
        )
        payload["status_history"] = [serialize_status_history(h) for h in history]
    if include_attachments:
        atts = [a for a in (job.attachments or []) if a.archived_at is None]
        atts.sort(
            key=lambda a: (a.created_at.isoformat() if a.created_at else "", str(a.id))
        )
        urls = attachment_urls or {}
        payload["attachments"] = [
            serialize_attachment(a, download_url=urls.get(str(a.id))) for a in atts
        ]
    return payload
