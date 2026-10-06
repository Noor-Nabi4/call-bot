"""Platform CRM module registry (configuration keys only — not domain CRUD)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ModuleDef:
    key: str
    name: str
    description: str = ""


CRM_MODULES: tuple[ModuleDef, ...] = (
    ModuleDef("CUSTOMERS", "Customers"),
    ModuleDef("LEADS", "Leads"),
    ModuleDef("PRODUCTS", "Products"),
    ModuleDef("CATEGORIES", "Categories"),
    ModuleDef("INVENTORY", "Inventory"),
    ModuleDef("ORDERS", "Orders"),
    ModuleDef("SERVICES", "Services"),
    ModuleDef("JOBS", "Jobs"),
    ModuleDef("APPOINTMENTS", "Appointments"),
    ModuleDef("DISPATCH", "Dispatch"),
    ModuleDef("TECHNICIANS", "Technicians"),
    ModuleDef("PROPERTIES", "Properties"),
    ModuleDef("EQUIPMENT", "Equipment"),
    ModuleDef("ESTIMATES", "Estimates"),
    ModuleDef("INVOICES", "Invoices"),
    ModuleDef("PAYMENTS", "Payments"),
    ModuleDef("MEMBERSHIPS", "Memberships"),
    ModuleDef("SHIPPING", "Shipping"),
    ModuleDef("RETURNS", "Returns"),
    ModuleDef("DISCOUNTS", "Discounts"),
    ModuleDef("CALLS", "Calls"),
)

MODULE_BY_KEY = {m.key: m for m in CRM_MODULES}
MODULE_KEYS: frozenset[str] = frozenset(MODULE_BY_KEY)


def list_modules() -> list[dict[str, str]]:
    return [
        {"key": m.key, "name": m.name, "description": m.description}
        for m in CRM_MODULES
    ]


def assert_module_keys(keys: list[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in keys:
        key = str(raw).strip().upper()
        if key not in MODULE_KEYS:
            raise ValueError(f"Unknown CRM module: {key}")
        if key in seen:
            continue
        seen.add(key)
        out.append(key)
    return out
