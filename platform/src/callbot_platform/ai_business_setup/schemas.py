"""Validated recommendation DTOs — AI output must pass these before review/persist."""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator

ConfidenceBand = Literal["high", "medium", "low"]


class ClarificationQuestion(BaseModel):
    model_config = {"extra": "forbid"}

    id: str = Field(min_length=1, max_length=64)
    prompt: str = Field(min_length=1, max_length=500)
    options: list[str] = Field(default_factory=list, max_length=6)


class BusinessProfileRec(BaseModel):
    model_config = {"extra": "forbid"}

    industry: str = Field(min_length=1, max_length=64)
    industry_confidence: ConfidenceBand = "medium"
    business_models: list[str] = Field(default_factory=list, max_length=8)
    business_model_confidence: ConfidenceBand = "medium"
    service_area: str | None = Field(default=None, max_length=255)
    customer_type: str | None = Field(default=None, max_length=64)
    field_service: bool = False
    appointment_based: bool = False
    membership_based: bool = False
    inventory_required: bool = False
    equipment_tracking_required: bool = False
    summary: str | None = Field(default=None, max_length=1000)


class ModuleRec(BaseModel):
    model_config = {"extra": "forbid"}

    key: str = Field(min_length=1, max_length=64)
    recommended: bool = True
    selected: bool = True
    reason: str = Field(default="", max_length=500)
    confidence: ConfidenceBand = "medium"


class CustomFieldRec(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=128)
    field_key: str = Field(min_length=1, max_length=64)
    entity: str = Field(min_length=1, max_length=64)  # CRM module key
    reason: str = Field(default="", max_length=500)
    selected: bool = True


class ServiceRec(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=2000)
    reason: str = Field(default="", max_length=500)
    selected: bool = True
    # Never invent prices — leave unset
    price: None = None


class ProductCategoryRec(BaseModel):
    model_config = {"extra": "forbid"}

    name: str = Field(min_length=1, max_length=255)
    reason: str = Field(default="", max_length=500)
    selected: bool = True


class AiConfigRec(BaseModel):
    model_config = {"extra": "forbid"}

    recommended: bool = True
    primary_purpose: str = Field(default="CUSTOMER_SERVICE_AND_BOOKING", max_length=64)
    tone: str | None = Field(default="professional_friendly", max_length=64)
    greeting_suggestion: str | None = Field(default=None, max_length=500)
    capabilities: list[str] = Field(default_factory=list, max_length=20)
    # Risky actions stay off until Phase 30 / explicit owner enablement
    risky_actions_disabled: list[str] = Field(
        default_factory=lambda: [
            "refunds",
            "payments",
            "destructive_cancellations",
            "external_system_writes",
        ]
    )


class SetupRecommendation(BaseModel):
    model_config = {"extra": "forbid"}

    business_profile: BusinessProfileRec
    modules: list[ModuleRec] = Field(default_factory=list, max_length=40)
    custom_fields: list[CustomFieldRec] = Field(default_factory=list, max_length=40)
    services: list[ServiceRec] = Field(default_factory=list, max_length=40)
    product_categories: list[ProductCategoryRec] = Field(
        default_factory=list, max_length=40
    )
    ai_configuration: AiConfigRec = Field(default_factory=AiConfigRec)
    clarifications: list[ClarificationQuestion] = Field(
        default_factory=list, max_length=3
    )
    source: Literal["heuristic", "openai", "edited"] = "heuristic"

    @field_validator("modules")
    @classmethod
    def _dedupe_modules(cls, value: list[ModuleRec]) -> list[ModuleRec]:
        seen: set[str] = set()
        out: list[ModuleRec] = []
        for item in value:
            key = item.key.strip().upper()
            if key in seen:
                continue
            seen.add(key)
            out.append(item.model_copy(update={"key": key}))
        return out


class AnalyzeRequest(BaseModel):
    model_config = {"extra": "forbid"}

    description: str = Field(min_length=8, max_length=4000)
    clarification_answers: dict[str, str] = Field(default_factory=dict)


class ConfirmRequest(BaseModel):
    model_config = {"extra": "forbid"}

    operation_id: str = Field(min_length=8, max_length=128)
    recommendation: SetupRecommendation
    create_services: bool = True
    apply_crm_modules: bool = True


def recommendation_to_dict(rec: SetupRecommendation) -> dict[str, Any]:
    return rec.model_dump(mode="json")
