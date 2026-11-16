"""Product catalog ORM models (Phase 5)."""

from __future__ import annotations

from callbot_platform.db.models.catalog.attribute import (
    ProductAttribute,
    ProductAttributeValue,
)
from callbot_platform.db.models.catalog.brand import ProductBrand
from callbot_platform.db.models.catalog.category import ProductCategory
from callbot_platform.db.models.catalog.image import ProductImage
from callbot_platform.db.models.catalog.product import Product
from callbot_platform.db.models.catalog.sku import CatalogSku
from callbot_platform.db.models.catalog.variant import (
    ProductVariant,
    ProductVariantAttributeValue,
)

__all__ = [
    "CatalogSku",
    "Product",
    "ProductAttribute",
    "ProductAttributeValue",
    "ProductBrand",
    "ProductCategory",
    "ProductImage",
    "ProductVariant",
    "ProductVariantAttributeValue",
]
