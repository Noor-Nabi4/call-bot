"""Business configuration catalogs package."""

from __future__ import annotations

from callbot_platform.business_config.industries import (
    INDUSTRIES,
    INDUSTRY_KEYS,
    list_industries,
    normalize_industry_key,
)
from callbot_platform.business_config.models_catalog import (
    BUSINESS_MODEL_KEYS,
    BUSINESS_MODELS,
    list_business_models,
)
from callbot_platform.business_config.modules import MODULE_KEYS, list_modules
from callbot_platform.business_config.sizes import (
    BUSINESS_SIZE_KEYS,
    list_business_sizes,
)

__all__ = [
    "BUSINESS_MODELS",
    "BUSINESS_MODEL_KEYS",
    "BUSINESS_SIZE_KEYS",
    "INDUSTRIES",
    "INDUSTRY_KEYS",
    "MODULE_KEYS",
    "list_business_models",
    "list_business_sizes",
    "list_industries",
    "list_modules",
    "normalize_industry_key",
]
