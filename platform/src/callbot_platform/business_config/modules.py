"""Platform CRM module registry (immutable definitions).

Organization enablement lives in ``organization_crm_modules``.
This registry is code-owned — tenants cannot mutate it.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True, slots=True)
class ModuleDef:
    key: str
    name: str
    description: str = ""
    icon: str = "box"
    category: str = "crm"
    default_order: int = 100
    supports_custom_fields: bool = True
    supports_relationships: bool = True
    supports_search: bool = True
    supports_archive: bool = True
    # Platform modules that must stay enabled for voice/ops integrity.
    required: bool = False
    # RBAC permission used for navigation / read access (catalog key).
    read_permission: str | None = None
    create_permission: str | None = None
    update_permission: str | None = None
    delete_permission: str | None = None
    # Existing ops UI path when a first-class page exists.
    href: str | None = None


def _m(
    key: str,
    name: str,
    *,
    description: str = "",
    icon: str = "box",
    category: str = "crm",
    default_order: int = 100,
    required: bool = False,
    read_permission: str | None = None,
    create_permission: str | None = None,
    update_permission: str | None = None,
    delete_permission: str | None = None,
    href: str | None = None,
    supports_custom_fields: bool = True,
    supports_relationships: bool = True,
) -> ModuleDef:
    return ModuleDef(
        key=key,
        name=name,
        description=description,
        icon=icon,
        category=category,
        default_order=default_order,
        required=required,
        read_permission=read_permission,
        create_permission=create_permission,
        update_permission=update_permission,
        delete_permission=delete_permission,
        href=href,
        supports_custom_fields=supports_custom_fields,
        supports_relationships=supports_relationships,
    )


# Ordered platform registry. Keys are stable machine identifiers.
CRM_MODULES: tuple[ModuleDef, ...] = (
    _m(
        "CUSTOMERS",
        "Customers",
        description="People and accounts who buy from you",
        icon="users",
        default_order=10,
        required=True,
        read_permission="customers.read",
        create_permission="customers.create",
        update_permission="customers.update",
        href="/customers",
    ),
    _m(
        "COMPANIES",
        "Companies",
        description="Business accounts and organizations",
        icon="building",
        default_order=15,
        read_permission="companies.read",
        create_permission="companies.create",
        update_permission="companies.update",
        delete_permission="companies.delete",
        href="/crm/companies",
    ),
    _m(
        "LEADS",
        "Leads",
        description="Inbound and outbound sales leads",
        icon="user-plus",
        default_order=20,
        read_permission="leads.read",
        create_permission="leads.create",
        href="/crm/leads",
    ),
    _m(
        "DEALS",
        "Deals",
        description="Sales opportunities and pipeline",
        icon="handshake",
        default_order=25,
        read_permission="deals.read",
        create_permission="deals.create",
        update_permission="deals.update",
        delete_permission="deals.delete",
        href="/crm/deals",
    ),
    _m(
        "PRODUCTS",
        "Products",
        description="Sellable products",
        icon="package",
        category="commerce",
        default_order=30,
        read_permission="products.read",
        create_permission="products.create",
        update_permission="products.update",
        delete_permission="products.delete",
        href="/crm/products",
    ),
    _m(
        "SERVICES",
        "Services",
        description="Service offerings",
        icon="wrench",
        category="operations",
        default_order=35,
        read_permission="services.read",
        create_permission="services.create",
        update_permission="services.update",
        delete_permission="services.delete",
        href="/crm/services",
    ),
    _m(
        "PRICEBOOKS",
        "Pricebooks",
        description="Service pricing and labor/material composition",
        icon="tag",
        category="commerce",
        default_order=36,
        read_permission="pricebooks.read",
        create_permission="pricebooks.create",
        update_permission="pricebooks.update",
        delete_permission="pricebooks.delete",
        href="/crm/pricebooks",
    ),
    _m(
        "ORDERS",
        "Orders",
        description="Customer orders (commerce ships later)",
        icon="shopping-cart",
        category="commerce",
        default_order=40,
        read_permission="orders.read",
        create_permission="orders.create",
        update_permission="orders.update",
        delete_permission="orders.delete",
        href="/crm/orders",
    ),
    _m(
        "JOBS",
        "Jobs",
        description="Field service jobs",
        icon="briefcase",
        category="operations",
        default_order=45,
        read_permission="jobs.read",
        create_permission="jobs.create",
        update_permission="jobs.update",
        delete_permission="jobs.delete",
        href="/crm/jobs",
    ),
    _m(
        "APPOINTMENTS",
        "Appointments",
        description="Scheduled visits and bookings",
        icon="calendar",
        category="operations",
        default_order=50,
        read_permission="appointments.read",
        create_permission="appointments.create",
        update_permission="appointments.update",
        href="/crm/appointments",
    ),
    _m(
        "ESTIMATES",
        "Estimates",
        description="Quotes and estimates",
        icon="file-text",
        category="billing",
        default_order=55,
        read_permission="estimates.read",
        create_permission="estimates.create",
        update_permission="estimates.update",
        delete_permission="estimates.delete",
        href="/crm/estimates",
    ),
    _m(
        "INVOICES",
        "Invoices",
        description="Customer invoices",
        icon="receipt",
        category="billing",
        default_order=60,
        read_permission="invoices.read",
        create_permission="invoices.create",
        update_permission="invoices.update",
        delete_permission="invoices.delete",
        href="/crm/invoices",
    ),
    _m(
        "PAYMENTS",
        "Payments",
        description="Payment records",
        icon="credit-card",
        category="billing",
        default_order=65,
        read_permission="payments.read",
        create_permission="payments.create",
        update_permission="payments.update",
        delete_permission="payments.delete",
        href="/crm/payments",
    ),
    _m(
        "EQUIPMENT",
        "Equipment",
        description="Installed or tracked equipment",
        icon="cpu",
        category="operations",
        default_order=70,
        read_permission="equipment.read",
        create_permission="equipment.create",
        update_permission="equipment.update",
        delete_permission="equipment.delete",
        href="/crm/equipment",
    ),
    _m(
        "MEMBERSHIPS",
        "Memberships",
        description="Recurring memberships and plans",
        icon="badge",
        category="commerce",
        default_order=75,
        read_permission="memberships.read",
        create_permission="memberships.create",
        update_permission="memberships.update",
        delete_permission="memberships.delete",
        href="/crm/memberships",
    ),
    _m(
        "CALLS",
        "Calls",
        description="Voice call history",
        icon="phone",
        category="communications",
        default_order=80,
        required=True,
        read_permission="calls.read",
        update_permission="calls.update",
        href="/calls",
        supports_custom_fields=False,
    ),
    _m(
        "CONVERSATIONS",
        "Conversations",
        description="Omnichannel conversation threads",
        icon="message-square",
        category="communications",
        default_order=85,
        read_permission="conversations.read",
        create_permission="conversations.create",
        update_permission="conversations.update",
        delete_permission="conversations.delete",
        href="/crm/conversations",
    ),
    _m(
        "TASKS",
        "Tasks",
        description="Follow-ups and work items",
        icon="check-square",
        category="operations",
        default_order=90,
        read_permission="tasks.read",
        create_permission="tasks.create",
        update_permission="tasks.update",
        delete_permission="tasks.delete",
        href="/crm/tasks",
    ),
    # Retained for industry templates from Phase 2 (still valid module keys).
    _m(
        "CATEGORIES",
        "Categories",
        description="Product/service categories",
        icon="folder",
        category="commerce",
        default_order=95,
        read_permission="products.read",
        href="/crm/categories",
    ),
    _m(
        "INVENTORY",
        "Inventory",
        description="Stock levels (commerce ships later)",
        icon="layers",
        category="commerce",
        default_order=96,
        read_permission="products.read",
        href="/crm/inventory",
    ),
    _m(
        "DISPATCH",
        "Dispatch",
        description="Dispatch board",
        icon="map",
        category="operations",
        default_order=47,
        read_permission="dispatch.read",
        href="/crm/dispatch",
        supports_custom_fields=False,
    ),
    _m(
        "TECHNICIANS",
        "Technicians",
        description="Field technicians",
        icon="hard-hat",
        category="operations",
        default_order=48,
        read_permission="technicians.read",
        update_permission="technicians.manage",
        href="/settings/team",
        supports_custom_fields=False,
    ),
    _m(
        "PROPERTIES",
        "Properties",
        description="Service locations and properties",
        icon="home",
        category="operations",
        default_order=72,
        read_permission="properties.read",
        create_permission="properties.create",
        update_permission="properties.update",
        delete_permission="properties.delete",
        href="/crm/properties",
    ),
    _m(
        "SHIPPING",
        "Shipping",
        description="Shipments",
        icon="truck",
        category="commerce",
        default_order=97,
        read_permission="orders.read",
        href="/crm/shipping",
    ),
    _m(
        "RETURNS",
        "Returns",
        description="Return merchandise",
        icon="rotate-ccw",
        category="commerce",
        default_order=98,
        read_permission="orders.read",
        href="/crm/returns",
    ),
    _m(
        "DISCOUNTS",
        "Discounts",
        description="Discount codes and promotions",
        icon="percent",
        category="commerce",
        default_order=99,
        read_permission="products.read",
        href="/crm/discounts",
    ),
)

MODULE_BY_KEY = {m.key: m for m in CRM_MODULES}
MODULE_KEYS: frozenset[str] = frozenset(MODULE_BY_KEY)

SOURCE_SYSTEM_DEFAULT = "SYSTEM_DEFAULT"
SOURCE_INDUSTRY_DEFAULT = "INDUSTRY_DEFAULT"
SOURCE_ORG_CUSTOM = "ORG_CUSTOM"
# Legacy Phase 2 sources normalized on read.
_SOURCE_ALIASES = {
    "template": SOURCE_INDUSTRY_DEFAULT,
    "custom": SOURCE_ORG_CUSTOM,
    "system": SOURCE_SYSTEM_DEFAULT,
}


def normalize_source(value: str | None) -> str:
    raw = (value or SOURCE_INDUSTRY_DEFAULT).strip()
    return _SOURCE_ALIASES.get(raw, raw)


def list_modules() -> list[dict[str, Any]]:
    return [serialize_module(m) for m in CRM_MODULES]


def serialize_module(m: ModuleDef) -> dict[str, Any]:
    return {
        "key": m.key,
        "name": m.name,
        "description": m.description,
        "icon": m.icon,
        "category": m.category,
        "default_order": m.default_order,
        "supports_custom_fields": m.supports_custom_fields,
        "supports_relationships": m.supports_relationships,
        "supports_search": m.supports_search,
        "supports_archive": m.supports_archive,
        "required": m.required,
        "read_permission": m.read_permission,
        "create_permission": m.create_permission,
        "update_permission": m.update_permission,
        "delete_permission": m.delete_permission,
        "href": m.href,
    }


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


def module_permission_map() -> dict[str, dict[str, str | None]]:
    return {
        m.key: {
            "read": m.read_permission,
            "create": m.create_permission,
            "update": m.update_permission,
            "delete": m.delete_permission,
        }
        for m in CRM_MODULES
    }
