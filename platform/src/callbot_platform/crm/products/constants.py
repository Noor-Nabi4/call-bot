"""Catalog status and measurement constants."""

from __future__ import annotations

from enum import Enum


class CatalogStatus(str, Enum):
    ACTIVE = "ACTIVE"
    INACTIVE = "INACTIVE"


CATALOG_STATUSES: frozenset[str] = frozenset(s.value for s in CatalogStatus)
DEFAULT_CATALOG_STATUS = CatalogStatus.ACTIVE.value

WEIGHT_UNITS: frozenset[str] = frozenset({"KG", "G", "LB", "OZ"})
DEFAULT_WEIGHT_UNIT = "KG"

SKU_OWNER_PRODUCT = "product"
SKU_OWNER_VARIANT = "variant"
