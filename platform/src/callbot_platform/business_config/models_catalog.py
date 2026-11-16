"""Business model catalog (what the business sells)."""

from __future__ import annotations

from dataclasses import dataclass

# Align with organization.validation.BUSINESS_TYPES
BUSINESS_MODEL_KEYS = frozenset(
    {
        "products",
        "services",
        "products_and_services",
        "subscriptions",
        "appointments",
        "rentals",
        "custom",
    }
)


@dataclass(frozen=True, slots=True)
class BusinessModelDef:
    key: str
    name: str
    description: str


BUSINESS_MODELS: tuple[BusinessModelDef, ...] = (
    BusinessModelDef("products", "Products", "Sell physical or digital products"),
    BusinessModelDef("services", "Services", "Deliver field or professional services"),
    BusinessModelDef(
        "products_and_services",
        "Products + Services",
        "Sell products and deliver services",
    ),
    BusinessModelDef("subscriptions", "Subscriptions", "Recurring membership plans"),
    BusinessModelDef("appointments", "Appointments", "Bookable appointment-based work"),
    BusinessModelDef("rentals", "Rentals", "Rent equipment or property"),
    BusinessModelDef("custom", "Custom", "Custom or hybrid model"),
)

BUSINESS_MODEL_BY_KEY = {m.key: m for m in BUSINESS_MODELS}


def list_business_models() -> list[dict[str, str]]:
    return [
        {"key": m.key, "name": m.name, "description": m.description}
        for m in BUSINESS_MODELS
    ]
