"""Equipment domain constants (Phase 21)."""

from __future__ import annotations

from enum import StrEnum


class EquipmentStatus(StrEnum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"
    RETIRED = "RETIRED"
    REMOVED = "REMOVED"


class WarrantyStatus(StrEnum):
    UNKNOWN = "UNKNOWN"
    NOT_ACTIVE = "NOT_ACTIVE"
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"


class AttachmentKind(StrEnum):
    PHOTO = "PHOTO"
    INSTALLATION = "INSTALLATION"
    REPAIR = "REPAIR"
    BEFORE = "BEFORE"
    AFTER = "AFTER"
    OTHER = "OTHER"


# Lifecycle: ACTIVE ↔ INACTIVE → RETIRED → REMOVED (archive). No physical delete when jobs exist.
VALID_STATUS_TRANSITIONS: dict[str, frozenset[str]] = {
    EquipmentStatus.ACTIVE.value: frozenset(
        {
            EquipmentStatus.INACTIVE.value,
            EquipmentStatus.RETIRED.value,
            EquipmentStatus.REMOVED.value,
        }
    ),
    EquipmentStatus.INACTIVE.value: frozenset(
        {
            EquipmentStatus.ACTIVE.value,
            EquipmentStatus.RETIRED.value,
            EquipmentStatus.REMOVED.value,
        }
    ),
    EquipmentStatus.RETIRED.value: frozenset({EquipmentStatus.REMOVED.value}),
    EquipmentStatus.REMOVED.value: frozenset(),
}

SELECTABLE_STATUSES = frozenset(
    {EquipmentStatus.ACTIVE.value, EquipmentStatus.INACTIVE.value}
)

ATTACHMENT_MAX_BYTES = 10 * 1024 * 1024
