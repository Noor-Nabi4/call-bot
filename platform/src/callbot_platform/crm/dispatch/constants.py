"""Dispatch domain constants (Phase 12)."""

from __future__ import annotations

from enum import Enum


class TechnicianOperationalStatusValue(str, Enum):
    AVAILABLE = "AVAILABLE"
    BUSY = "BUSY"
    EN_ROUTE = "EN_ROUTE"
    ARRIVED = "ARRIVED"
    ON_BREAK = "ON_BREAK"
    OFFLINE = "OFFLINE"


TECHNICIAN_OPERATIONAL_STATUSES: frozenset[str] = frozenset(
    s.value for s in TechnicianOperationalStatusValue
)
DEFAULT_TECHNICIAN_STATUS = TechnicianOperationalStatusValue.OFFLINE.value

# Operational statuses that reject new dispatch assignment.
UNASSIGNABLE_TECH_STATUSES: frozenset[str] = frozenset(
    {
        TechnicianOperationalStatusValue.OFFLINE.value,
        TechnicianOperationalStatusValue.ON_BREAK.value,
    }
)

VALID_TECH_STATUS_TRANSITIONS: frozenset[tuple[str, str]] = frozenset(
    {
        ("AVAILABLE", "BUSY"),
        ("AVAILABLE", "ON_BREAK"),
        ("AVAILABLE", "OFFLINE"),
        ("BUSY", "AVAILABLE"),
        ("BUSY", "EN_ROUTE"),
        ("BUSY", "ON_BREAK"),
        ("BUSY", "OFFLINE"),
        ("EN_ROUTE", "ARRIVED"),
        ("EN_ROUTE", "AVAILABLE"),
        ("EN_ROUTE", "OFFLINE"),
        ("ARRIVED", "BUSY"),
        ("ARRIVED", "AVAILABLE"),
        ("ON_BREAK", "AVAILABLE"),
        ("ON_BREAK", "OFFLINE"),
        ("OFFLINE", "AVAILABLE"),
    }
)

ETA_SOURCES: frozenset[str] = frozenset({"SCHEDULE", "GPS", "ROUTING", "MANUAL", "AI"})

DISPATCH_EVENT_JOB_ASSIGNED = "JOB_ASSIGNED"
DISPATCH_EVENT_JOB_UNASSIGNED = "JOB_UNASSIGNED"
DISPATCH_EVENT_JOB_REASSIGNED = "JOB_REASSIGNED"
DISPATCH_EVENT_JOB_STATUS_CHANGED = "JOB_STATUS_CHANGED"
DISPATCH_EVENT_TECHNICIAN_STATUS_CHANGED = "TECHNICIAN_STATUS_CHANGED"
DISPATCH_EVENT_APPOINTMENT_CHANGED = "APPOINTMENT_CHANGED"
DISPATCH_EVENT_ETA_CHANGED = "ETA_CHANGED"


def normalize_tech_status(value: str) -> str:
    key = (value or "").strip().upper().replace("-", "_").replace(" ", "_")
    if key not in TECHNICIAN_OPERATIONAL_STATUSES:
        raise ValueError(f"unknown_technician_status:{value}")
    return key


def transitions_map() -> dict[str, frozenset[str]]:
    out: dict[str, set[str]] = {s: set() for s in TECHNICIAN_OPERATIONAL_STATUSES}
    for src, dst in VALID_TECH_STATUS_TRANSITIONS:
        out[src].add(dst)
    return {k: frozenset(v) for k, v in out.items()}
