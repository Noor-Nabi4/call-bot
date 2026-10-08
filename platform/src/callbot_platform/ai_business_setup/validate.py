"""Validate recommendation against canonical catalogs — never trust raw model output."""

from __future__ import annotations

from typing import Any

from callbot_platform.ai_business_setup.errors import AiBusinessSetupError
from callbot_platform.ai_business_setup.schemas import SetupRecommendation
from callbot_platform.business_config.industries import (
    INDUSTRY_KEYS,
    normalize_industry_key,
)
from callbot_platform.business_config.models_catalog import BUSINESS_MODEL_KEYS
from callbot_platform.business_config.modules import MODULE_KEYS


def validate_recommendation_payload(raw: dict[str, Any]) -> SetupRecommendation:
    try:
        rec = SetupRecommendation.model_validate(raw)
    except Exception as exc:
        raise AiBusinessSetupError(
            "AI_CONFIGURATION_INVALID",
            "AI recommendation failed schema validation",
        ) from exc

    industry = normalize_industry_key(rec.business_profile.industry)
    if industry not in INDUSTRY_KEYS:
        raise AiBusinessSetupError(
            "INVALID_INDUSTRY",
            f"Unsupported industry: {rec.business_profile.industry}",
        )
    rec.business_profile.industry = industry

    models: list[str] = []
    for m in rec.business_profile.business_models:
        key = m.strip().lower().replace(" ", "_").replace("-", "_")
        aliases = {
            "products_services": "products_and_services",
            "product_and_services": "products_and_services",
            "product_services": "products_and_services",
            "field_service": "services",
            "recurring": "subscriptions",
            "membership": "subscriptions",
            "appointment": "appointments",
        }
        key = aliases.get(key, key)
        if key not in BUSINESS_MODEL_KEYS:
            raise AiBusinessSetupError(
                "INVALID_BUSINESS_MODEL", f"Unsupported business model: {m}"
            )
        if key not in models:
            models.append(key)
    if not models:
        models = ["services"]
    rec.business_profile.business_models = models

    for mod in rec.modules:
        if mod.key not in MODULE_KEYS:
            raise AiBusinessSetupError(
                "INVALID_MODULE", f"Unknown CRM module: {mod.key}"
            )

    for field in rec.custom_fields:
        entity = field.entity.strip().upper()
        if entity not in MODULE_KEYS:
            raise AiBusinessSetupError(
                "INVALID_MODULE", f"Unknown custom-field entity module: {entity}"
            )
        field.entity = entity
        fk = field.field_key.strip().lower().replace(" ", "_").replace("-", "_")[:64]
        if not fk:
            raise AiBusinessSetupError("INVALID_FIELD", "Custom field key required")
        field.field_key = fk

    return rec
