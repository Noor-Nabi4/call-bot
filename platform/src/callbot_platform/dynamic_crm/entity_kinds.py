"""Entity target classification for CRM relationships.

PLATFORM_ENTITY  — materialized relational table exists
CUSTOM_OBJECT    — organization custom object records
CONFIGURATION_ONLY — module enabled in CRM config but no record table yet
"""

from __future__ import annotations

from typing import Final

ENTITY_KIND_PLATFORM = "PLATFORM_ENTITY"
ENTITY_KIND_CUSTOM_OBJECT = "CUSTOM_OBJECT"
ENTITY_KIND_CONFIGURATION_ONLY = "CONFIGURATION_ONLY"

# Modules with real tenant-scoped rows today (not Phase 4 commerce).
PLATFORM_MODULE_TABLES: Final[frozenset[str]] = frozenset(
    {
        "CUSTOMERS",
        "LEADS",
        "CALLS",
        "JOBS",
        "APPOINTMENTS",
        "TECHNICIANS",
        "PRODUCTS",
    }
)


def classify_module_entity(module_key: str) -> str:
    key = module_key.strip().upper()
    if key in PLATFORM_MODULE_TABLES:
        return ENTITY_KIND_PLATFORM
    return ENTITY_KIND_CONFIGURATION_ONLY


def relationship_record_supported(*, entity_type: str, entity_key: str) -> bool:
    et = entity_type.strip().lower()
    if et == "object":
        return True
    if et == "module":
        return classify_module_entity(entity_key) == ENTITY_KIND_PLATFORM
    return False
