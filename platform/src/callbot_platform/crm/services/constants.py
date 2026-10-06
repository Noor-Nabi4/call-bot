"""Services & Pricebook constants."""

from __future__ import annotations

from enum import Enum


class CatalogStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


CATALOG_STATUSES: frozenset[str] = frozenset(s.value for s in CatalogStatus)
DEFAULT_STATUS = CatalogStatus.ACTIVE.value


class PricingType(str, Enum):
    FIXED = "FIXED"
    STARTING_AT = "STARTING_AT"
    HOURLY = "HOURLY"
    CUSTOM_QUOTE = "CUSTOM_QUOTE"


PRICING_TYPES: frozenset[str] = frozenset(p.value for p in PricingType)
DEFAULT_PRICING_TYPE = PricingType.FIXED.value


class ComponentType(str, Enum):
    LABOR = "LABOR"
    MATERIAL = "MATERIAL"


COMPONENT_TYPES: frozenset[str] = frozenset(c.value for c in ComponentType)

# Price resolution sources (deterministic precedence documentation).
PRICE_SOURCE_OVERRIDE = "organization_override"
PRICE_SOURCE_PRICEBOOK_ITEM = "pricebook_item"
PRICE_SOURCE_SERVICE_BASE = "service_base"
PRICE_SOURCE_NO_PRICE = "no_price"
