"""Canonical request fingerprint for Appointment create idempotency."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime
from uuid import UUID


def _iso(value: datetime | None) -> str | None:
    if value is None:
        return None
    return value.isoformat()


def appointment_create_fingerprint(
    *,
    customer_id: UUID,
    location_id: UUID | None,
    service_id: UUID | None,
    service_type: str,
    technician_id: UUID | None,
    job_id: UUID | None,
    lead_id: UUID | None,
    call_id: UUID | None,
    starts_at: datetime,
    ends_at: datetime,
    priority: str,
    is_emergency: bool,
    status: str,
    notes: str | None,
) -> str:
    """Stable hash of material create fields (ignores actor / timestamps)."""
    payload = {
        "call_id": str(call_id) if call_id else None,
        "customer_id": str(customer_id),
        "ends_at": _iso(ends_at),
        "is_emergency": bool(is_emergency),
        "job_id": str(job_id) if job_id else None,
        "lead_id": str(lead_id) if lead_id else None,
        "location_id": str(location_id) if location_id else None,
        "notes": notes,
        "priority": priority,
        "service_id": str(service_id) if service_id else None,
        "service_type": service_type,
        "starts_at": _iso(starts_at),
        "status": status,
        "technician_id": str(technician_id) if technician_id else None,
    }
    raw = json.dumps(payload, sort_keys=True, separators=(",", ":"), default=str)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
