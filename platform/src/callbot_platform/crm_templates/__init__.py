"""Platform-owned industry CRM templates (immutable at runtime by tenants)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from callbot_platform.business_config.modules import MODULE_KEYS, assert_module_keys


@dataclass(frozen=True, slots=True)
class CrmTemplate:
    key: str
    name: str
    industries: tuple[str, ...]
    business_models: tuple[str, ...]
    modules: tuple[str, ...]
    settings: dict[str, Any] = field(default_factory=dict)
    statuses: dict[str, tuple[str, ...]] = field(default_factory=dict)
    fields: dict[str, tuple[dict[str, str], ...]] = field(default_factory=dict)
    workflows: tuple[dict[str, Any], ...] = field(default_factory=tuple)
    version: int = 1


def _svc_statuses() -> dict[str, tuple[str, ...]]:
    return {
        "JOBS": ("NEW", "SCHEDULED", "IN_PROGRESS", "COMPLETED", "CANCELLED"),
        "APPOINTMENTS": (
            "REQUESTED",
            "CONFIRMED",
            "COMPLETED",
            "CANCELLED",
            "NO_SHOW",
        ),
        "LEADS": ("NEW", "CONTACTED", "QUALIFIED", "WON", "LOST"),
        "ESTIMATES": ("DRAFT", "SENT", "ACCEPTED", "DECLINED", "EXPIRED"),
        "INVOICES": ("DRAFT", "SENT", "PAID", "OVERDUE", "VOID"),
    }


def _commerce_statuses() -> dict[str, tuple[str, ...]]:
    return {
        "ORDERS": ("PENDING", "CONFIRMED", "FULFILLED", "CANCELLED"),
        "LEADS": ("NEW", "CONTACTED", "QUALIFIED", "WON", "LOST"),
    }


def _field_trade() -> dict[str, tuple[dict[str, str], ...]]:
    return {
        "EQUIPMENT": (
            {"key": "equipment_type", "label": "Equipment type"},
            {"key": "equipment_model", "label": "Model"},
            {"key": "installation_year", "label": "Installation year"},
        ),
        "PROPERTIES": ({"key": "property_type", "label": "Property type"},),
    }


def _field_commerce() -> dict[str, tuple[dict[str, str], ...]]:
    return {
        "CUSTOMERS": (
            {"key": "customer_segment", "label": "Customer segment"},
            {"key": "preferred_shipping_method", "label": "Preferred shipping"},
        ),
    }


def _wf_job() -> tuple[dict[str, Any], ...]:
    return (
        {
            "key": "job_lifecycle",
            "name": "Job lifecycle",
            "module_key": "JOBS",
            "stages": [
                "NEW",
                "SCHEDULED",
                "IN_PROGRESS",
                "COMPLETED",
                "INVOICE",
            ],
        },
    )


def _wf_lead() -> tuple[dict[str, Any], ...]:
    return (
        {
            "key": "lead_pipeline",
            "name": "Lead pipeline",
            "module_key": "LEADS",
            "stages": ["NEW", "CONTACTED", "QUALIFIED", "APPOINTMENT"],
        },
    )


_DEFAULT_SETTINGS: dict[str, Any] = {
    "appointment_duration_minutes": 60,
    "booking_buffer_minutes": 15,
    "estimate_expiration_days": 30,
}


def _tpl(
    key: str,
    name: str,
    industries: tuple[str, ...],
    modules: tuple[str, ...],
    *,
    business_models: tuple[str, ...] = (
        "services",
        "products_and_services",
        "appointments",
        "subscriptions",
        "custom",
    ),
    statuses: dict[str, tuple[str, ...]] | None = None,
    fields: dict[str, tuple[dict[str, str], ...]] | None = None,
    workflows: tuple[dict[str, Any], ...] | None = None,
) -> CrmTemplate:
    mods = tuple(assert_module_keys(list(modules)))
    return CrmTemplate(
        key=key,
        name=name,
        industries=industries,
        business_models=business_models,
        modules=mods,
        settings=dict(_DEFAULT_SETTINGS),
        statuses=statuses or _svc_statuses(),
        fields=fields or {},
        workflows=workflows or (_wf_job() + _wf_lead()),
        version=1,
    )


TEMPLATES: tuple[CrmTemplate, ...] = (
    _tpl(
        "hvac",
        "HVAC",
        ("hvac",),
        (
            "CUSTOMERS",
            "PROPERTIES",
            "EQUIPMENT",
            "SERVICES",
            "JOBS",
            "APPOINTMENTS",
            "DISPATCH",
            "TECHNICIANS",
            "ESTIMATES",
            "INVOICES",
            "PAYMENTS",
            "MEMBERSHIPS",
            "LEADS",
            "CALLS",
        ),
        fields=_field_trade(),
    ),
    _tpl(
        "plumbing",
        "Plumbing",
        ("plumbing",),
        (
            "CUSTOMERS",
            "PROPERTIES",
            "EQUIPMENT",
            "SERVICES",
            "JOBS",
            "APPOINTMENTS",
            "DISPATCH",
            "TECHNICIANS",
            "ESTIMATES",
            "INVOICES",
            "PAYMENTS",
            "LEADS",
            "CALLS",
        ),
        fields=_field_trade(),
    ),
    _tpl(
        "electrical",
        "Electrical",
        ("electrical",),
        (
            "CUSTOMERS",
            "PROPERTIES",
            "SERVICES",
            "JOBS",
            "APPOINTMENTS",
            "DISPATCH",
            "TECHNICIANS",
            "ESTIMATES",
            "INVOICES",
            "PAYMENTS",
            "LEADS",
            "CALLS",
        ),
    ),
    _tpl(
        "cleaning",
        "Cleaning",
        ("cleaning",),
        (
            "CUSTOMERS",
            "PROPERTIES",
            "SERVICES",
            "APPOINTMENTS",
            "JOBS",
            "TECHNICIANS",
            "ESTIMATES",
            "INVOICES",
            "PAYMENTS",
            "MEMBERSHIPS",
            "LEADS",
            "CALLS",
        ),
    ),
    _tpl(
        "automotive",
        "Automotive",
        ("automotive",),
        (
            "CUSTOMERS",
            "SERVICES",
            "JOBS",
            "APPOINTMENTS",
            "TECHNICIANS",
            "ESTIMATES",
            "INVOICES",
            "PAYMENTS",
            "LEADS",
            "CALLS",
        ),
    ),
    _tpl(
        "dental",
        "Dental",
        ("dental",),
        (
            "CUSTOMERS",
            "APPOINTMENTS",
            "SERVICES",
            "INVOICES",
            "PAYMENTS",
            "MEMBERSHIPS",
            "LEADS",
            "CALLS",
        ),
        business_models=("appointments", "services", "subscriptions", "custom"),
    ),
    _tpl(
        "medical",
        "Medical",
        ("medical",),
        (
            "CUSTOMERS",
            "APPOINTMENTS",
            "SERVICES",
            "INVOICES",
            "PAYMENTS",
            "LEADS",
            "CALLS",
        ),
        business_models=("appointments", "services", "subscriptions", "custom"),
    ),
    _tpl(
        "real_estate",
        "Real Estate",
        ("real_estate",),
        (
            "CUSTOMERS",
            "PROPERTIES",
            "APPOINTMENTS",
            "LEADS",
            "ESTIMATES",
            "CALLS",
        ),
        business_models=("services", "appointments", "custom"),
    ),
    _tpl(
        "ecommerce",
        "E-commerce",
        ("ecommerce",),
        (
            "CUSTOMERS",
            "PRODUCTS",
            "CATEGORIES",
            "INVENTORY",
            "ORDERS",
            "PAYMENTS",
            "SHIPPING",
            "RETURNS",
            "DISCOUNTS",
            "LEADS",
            "CALLS",
        ),
        business_models=("products", "subscriptions", "custom"),
        statuses=_commerce_statuses(),
        fields=_field_commerce(),
        workflows=(
            {
                "key": "order_fulfillment",
                "name": "Order fulfillment",
                "module_key": "ORDERS",
                "stages": ["PENDING", "CONFIRMED", "FULFILLED"],
            },
        ),
    ),
    _tpl(
        "consulting",
        "Consulting",
        ("consulting",),
        (
            "CUSTOMERS",
            "LEADS",
            "APPOINTMENTS",
            "SERVICES",
            "ESTIMATES",
            "INVOICES",
            "PAYMENTS",
            "CALLS",
        ),
        business_models=("services", "appointments", "subscriptions", "custom"),
    ),
    _tpl(
        "beauty_salon",
        "Beauty / Salon",
        ("beauty_salon",),
        (
            "CUSTOMERS",
            "APPOINTMENTS",
            "SERVICES",
            "MEMBERSHIPS",
            "PAYMENTS",
            "INVOICES",
            "LEADS",
            "CALLS",
        ),
        business_models=("appointments", "services", "subscriptions", "custom"),
    ),
    _tpl(
        "fitness",
        "Fitness",
        ("fitness",),
        (
            "CUSTOMERS",
            "MEMBERSHIPS",
            "APPOINTMENTS",
            "SERVICES",
            "PAYMENTS",
            "INVOICES",
            "LEADS",
            "CALLS",
        ),
        business_models=("subscriptions", "appointments", "services", "custom"),
    ),
    _tpl(
        "custom",
        "Custom / Generic",
        ("custom",),
        ("CUSTOMERS", "LEADS", "APPOINTMENTS", "CALLS"),
        business_models=(
            "products",
            "services",
            "products_and_services",
            "subscriptions",
            "appointments",
            "rentals",
            "custom",
        ),
        statuses={
            "LEADS": ("NEW", "CONTACTED", "QUALIFIED", "WON", "LOST"),
            "APPOINTMENTS": (
                "REQUESTED",
                "CONFIRMED",
                "COMPLETED",
                "CANCELLED",
                "NO_SHOW",
            ),
        },
        workflows=_wf_lead(),
    ),
)

TEMPLATE_BY_KEY: dict[str, CrmTemplate] = {t.key: t for t in TEMPLATES}


def list_templates() -> list[dict[str, Any]]:
    return [
        {
            "key": t.key,
            "name": t.name,
            "industries": list(t.industries),
            "business_models": list(t.business_models),
            "modules": list(t.modules),
            "version": t.version,
        }
        for t in TEMPLATES
    ]


def get_template(key: str) -> CrmTemplate | None:
    return TEMPLATE_BY_KEY.get(key.strip().lower())


def resolve_template(
    *, industry_key: str | None, business_model: str | None
) -> CrmTemplate:
    """Deterministic template resolution from industry (+ optional model filter)."""
    industry = (industry_key or "custom").strip().lower()
    model = (business_model or "custom").strip().lower()

    # Prefer exact industry match.
    for tmpl in TEMPLATES:
        if industry in tmpl.industries:
            if model in tmpl.business_models or not tmpl.business_models:
                return tmpl
            # Industry match but model mismatch — still use industry template.
            return tmpl

    # Products-heavy fallback when industry unknown.
    if model == "products":
        ecommerce = TEMPLATE_BY_KEY["ecommerce"]
        return ecommerce

    return TEMPLATE_BY_KEY["custom"]


def serialize_template(tmpl: CrmTemplate) -> dict[str, Any]:
    return {
        "key": tmpl.key,
        "name": tmpl.name,
        "industries": list(tmpl.industries),
        "business_models": list(tmpl.business_models),
        "modules": list(tmpl.modules),
        "settings": dict(tmpl.settings),
        "statuses": {k: list(v) for k, v in tmpl.statuses.items()},
        "fields": {k: [dict(f) for f in v] for k, v in tmpl.fields.items()},
        "workflows": [dict(w) for w in tmpl.workflows],
        "version": tmpl.version,
        "mutable": False,
    }


# Validate registry integrity at import.
for _t in TEMPLATES:
    for _m in _t.modules:
        if _m not in MODULE_KEYS:
            raise RuntimeError(f"Template {_t.key} has invalid module {_m}")
    if len(_t.modules) != len(set(_t.modules)):
        raise RuntimeError(f"Template {_t.key} has duplicate modules")
