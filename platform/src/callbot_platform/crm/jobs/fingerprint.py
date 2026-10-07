"""Canonical request fingerprint for Job create idempotency."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def job_create_fingerprint(
    *,
    customer_id: UUID,
    service_id: UUID | None,
    service_type: str,
    location_id: UUID | None,
    equipment_id: UUID | None = None,
    description: str | None,
    priority: str,
    technician_id: UUID | None,
    scheduled_starts_at: datetime | None,
    scheduled_ends_at: datetime | None,
    appointment_id: UUID | None,
    lead_id: UUID | None,
    call_id: UUID | None,
    status: str,
) -> str:
    """Stable hash of material create fields (ignores actor / timestamps)."""
    payload = {
        "appointment_id": str(appointment_id) if appointment_id else None,
        "call_id": str(call_id) if call_id else None,
        "customer_id": str(customer_id),
        "description": description,
        "lead_id": str(lead_id) if lead_id else None,
        "location_id": str(location_id) if location_id else None,
        "equipment_id": str(equipment_id) if equipment_id else None,
        "priority": priority,
        "scheduled_ends_at": _iso(scheduled_ends_at),
        "scheduled_starts_at": _iso(scheduled_starts_at),
        "service_id": str(service_id) if service_id else None,
        "service_type": service_type,
        "status": status,
        "technician_id": str(technician_id) if technician_id else None,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
