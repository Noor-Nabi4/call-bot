"""Global geo reference catalogs (countries, regions, currencies, timezones)."""

from __future__ import annotations

from callbot_platform.geo.seed import ensure_geo_catalog
from callbot_platform.geo.service import GeoCatalogService

__all__ = ["GeoCatalogService", "ensure_geo_catalog"]
