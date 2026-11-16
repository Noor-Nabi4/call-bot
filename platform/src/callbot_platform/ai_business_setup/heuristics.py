"""Deterministic recommendation engine — works without an LLM provider.

Uses existing industry templates + keyword signals from the business description.
OpenAI (when configured) may refine; validate.py still gates all output.
"""

from __future__ import annotations

import re
from typing import Any

from callbot_platform.ai_business_setup.schemas import (
    AiConfigRec,
    BusinessProfileRec,
    ClarificationQuestion,
    CustomFieldRec,
    ModuleRec,
    ProductCategoryRec,
    ServiceRec,
    SetupRecommendation,
)
from callbot_platform.business_config.industries import (
    INDUSTRY_BY_KEY,
    normalize_industry_key,
)
from callbot_platform.business_config.modules import MODULE_BY_KEY
from callbot_platform.crm_templates import resolve_template, serialize_template

_INDUSTRY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hvac": (
        "hvac",
        "air conditioning",
        "ac repair",
        "furnace",
        "heat pump",
        "refrigerant",
    ),
    "plumbing": ("plumb", "pipe", "drain", "water heater", "faucet"),
    "electrical": ("electric", "wiring", "breaker", "panel"),
    "cleaning": ("clean", "janitor", "maid", "housekeeping"),
    "automotive": ("auto repair", "mechanic", "car service", "vehicle"),
    "dental": ("dental", "dentist", "orthodont"),
    "medical": ("clinic", "medical", "patient", "physician"),
    "real_estate": ("real estate", "realtor", "brokerage", "property listing"),
    "ecommerce": (
        "ecommerce",
        "e-commerce",
        "online store",
        "shopify",
        "retail online",
    ),
    "fitness": ("gym", "fitness", "workout", "personal train"),
    "beauty_salon": ("salon", "spa", "beauty", "barber"),
    "consulting": ("consult", "advisory", "professional services"),
}

_SERVICE_HINTS: dict[str, tuple[str, ...]] = {
    "hvac": (
        "AC Repair",
        "AC Installation",
        "AC Maintenance",
        "Furnace Repair",
        "HVAC Inspection",
    ),
    "plumbing": (
        "Drain Cleaning",
        "Leak Repair",
        "Water Heater Service",
        "Fixture Installation",
    ),
    "electrical": (
        "Electrical Repair",
        "Panel Upgrade",
        "Outlet Installation",
        "Safety Inspection",
    ),
    "cleaning": (
        "Residential Cleaning",
        "Commercial Cleaning",
        "Deep Clean",
        "Recurring Maintenance Clean",
    ),
}

_PRODUCT_HINTS: dict[str, tuple[str, ...]] = {
    "hvac": (
        "Air Conditioners",
        "Heat Pumps",
        "Thermostats",
        "Filters",
        "HVAC Accessories",
    ),
    "ecommerce": ("Bestsellers", "Accessories", "Core Catalog"),
}

_EXTRA_FIELDS: dict[str, list[tuple[str, str, str]]] = {
    # entity, field_key, label
    "hvac": [
        ("EQUIPMENT", "manufacturer", "Manufacturer"),
        ("EQUIPMENT", "serial_number", "Serial number"),
        ("EQUIPMENT", "refrigerant_type", "Refrigerant type"),
        ("EQUIPMENT", "warranty_expiration", "Warranty expiration"),
        (
            "CUSTOMERS",
            "preferred_maintenance_schedule",
            "Preferred maintenance schedule",
        ),
    ],
    "plumbing": [
        ("EQUIPMENT", "pipe_type", "Pipe type"),
        ("EQUIPMENT", "water_heater_type", "Water heater type"),
        ("PROPERTIES", "fixture_type", "Fixture type"),
    ],
}


def _contains_any(text: str, words: tuple[str, ...]) -> bool:
    return any(w in text for w in words)


def classify_industry(description: str) -> tuple[str, str]:
    text = description.lower()
    scores: list[tuple[str, int]] = []
    for key, words in _INDUSTRY_KEYWORDS.items():
        hits = sum(1 for w in words if w in text)
        if hits:
            scores.append((key, hits))
    if not scores:
        return "custom", "low"
    scores.sort(key=lambda x: (-x[1], x[0]))
    best, hits = scores[0]
    if hits >= 2 or (hits == 1 and len(scores) == 1):
        return best, "high"
    if len(scores) > 1 and scores[0][1] == scores[1][1]:
        return best, "low"
    return best, "medium"


def detect_business_models(description: str, *, industry: str) -> tuple[list[str], str]:
    text = description.lower()
    models: list[str] = []
    sells_products = _contains_any(
        text, ("sell", "product", "equipment", "parts", "retail", "inventory")
    )
    sells_services = _contains_any(
        text, ("repair", "install", "service", "maintain", "inspect", "consult")
    ) or industry in {
        "hvac",
        "plumbing",
        "electrical",
        "cleaning",
        "automotive",
        "dental",
        "medical",
    }
    membership = _contains_any(
        text, ("membership", "maintenance plan", "annual plan", "subscription")
    )
    appointments = _contains_any(
        text, ("appoint", "book", "schedule", "visit")
    ) or industry in {"dental", "medical", "beauty_salon", "fitness"}

    if sells_products and sells_services:
        models.append("products_and_services")
    elif sells_products:
        models.append("products")
    elif sells_services:
        models.append("services")
    else:
        models.append("custom")

    if membership and "subscriptions" not in models:
        models.append("subscriptions")
    if appointments and "appointments" not in models:
        models.append("appointments")

    conf = "high" if sells_products or sells_services else "medium"
    return models, conf


def _module_reason(key: str, profile: BusinessProfileRec) -> str:
    name = MODULE_BY_KEY[key].name if key in MODULE_BY_KEY else key
    if key == "EQUIPMENT" and profile.equipment_tracking_required:
        return f"{name} helps track installed systems and service history."
    if key == "MEMBERSHIPS" and profile.membership_based:
        return f"{name} supports recurring maintenance plans mentioned in your description."
    if key == "INVENTORY" and profile.inventory_required:
        return f"{name} is useful when you stock parts or sell products."
    if key in {"JOBS", "DISPATCH", "TECHNICIANS"} and profile.field_service:
        return f"{name} supports field service operations."
    if key == "APPOINTMENTS" and profile.appointment_based:
        return f"{name} supports booking and scheduling."
    if key == "CALLS":
        return "Required for AI calling and call history."
    if key == "CUSTOMERS":
        return "Required for managing your customers."
    return (
        f"{name} is commonly used for {profile.industry.replace('_', ' ')} businesses."
    )


def build_clarifications(
    description: str, *, industry: str, models: list[str]
) -> list[ClarificationQuestion]:
    text = description.lower()
    qs: list[ClarificationQuestion] = []
    if industry == "custom" or (
        industry in {"hvac", "plumbing", "electrical"}
        and "products_and_services" not in models
        and "products" not in models
        and not _contains_any(text, ("sell", "product", "parts"))
    ):
        qs.append(
            ClarificationQuestion(
                id="sells_equipment",
                prompt=f"Do you sell {industry.replace('_', ' ')} equipment or parts directly to customers?",
                options=["Yes", "No", "Sometimes"],
            )
        )
    if industry in {"hvac", "plumbing", "cleaning"} and "membership" not in text:
        qs.append(
            ClarificationQuestion(
                id="offers_membership",
                prompt="Do you offer recurring maintenance plans or memberships?",
                options=["Yes", "No", "Planning to"],
            )
        )
    return qs[:3]


def apply_clarification_answers(
    models: list[str],
    profile_flags: dict[str, bool],
    answers: dict[str, str],
) -> tuple[list[str], dict[str, bool]]:
    models = list(models)
    flags = dict(profile_flags)
    sell = (answers.get("sells_equipment") or "").strip().lower()
    if sell in {"yes", "sometimes"}:
        flags["inventory_required"] = True
        if "products" not in models and "products_and_services" not in models:
            if "services" in models:
                models = [
                    "products_and_services" if m == "services" else m for m in models
                ]
            else:
                models.append("products")
    mem = (answers.get("offers_membership") or "").strip().lower()
    if mem in {"yes", "planning to"}:
        flags["membership_based"] = True
        if "subscriptions" not in models:
            models.append("subscriptions")
    return models, flags


def build_heuristic_recommendation(
    description: str,
    *,
    clarification_answers: dict[str, str] | None = None,
) -> SetupRecommendation:
    answers = clarification_answers or {}
    industry, ind_conf = classify_industry(description)
    industry = normalize_industry_key(industry)
    models, model_conf = detect_business_models(description, industry=industry)

    text = description.lower()
    flags = {
        "field_service": industry
        in {"hvac", "plumbing", "electrical", "cleaning", "automotive"}
        or _contains_any(text, ("field", "on-site", "technician", "dispatch")),
        "appointment_based": "appointments" in models
        or _contains_any(text, ("appoint", "book", "schedule")),
        "membership_based": "subscriptions" in models
        or _contains_any(text, ("membership", "maintenance plan")),
        "inventory_required": "products" in models
        or "products_and_services" in models
        or _contains_any(text, ("inventory", "stock", "parts")),
        "equipment_tracking_required": industry in {"hvac", "plumbing", "electrical"}
        or _contains_any(text, ("equipment", "serial", "installed system")),
    }
    models, flags = apply_clarification_answers(models, flags, answers)

    clarifications: list[ClarificationQuestion] = []
    if not answers:
        clarifications = build_clarifications(
            description, industry=industry, models=models
        )
        # Only ask clarifications when confidence is low or key signals missing.
        if ind_conf == "high" and model_conf == "high" and len(clarifications) > 1:
            clarifications = clarifications[:1]
        if ind_conf == "high" and _contains_any(
            text, ("maintenance plan", "membership", "sell", "parts")
        ):
            clarifications = []

    primary_model = models[0]
    tmpl = resolve_template(industry_key=industry, business_model=primary_model)
    tmpl_data = serialize_template(tmpl)

    profile = BusinessProfileRec(
        industry=industry,
        industry_confidence=ind_conf,  # type: ignore[arg-type]
        business_models=models,
        business_model_confidence=model_conf,  # type: ignore[arg-type]
        service_area=_guess_area(description),
        customer_type="residential"
        if "residential" in text
        else ("commercial" if "commercial" in text else None),
        field_service=flags["field_service"],
        appointment_based=flags["appointment_based"],
        membership_based=flags["membership_based"],
        inventory_required=flags["inventory_required"],
        equipment_tracking_required=flags["equipment_tracking_required"],
        summary=(
            INDUSTRY_BY_KEY.get(industry).name
            if industry in INDUSTRY_BY_KEY
            else industry
        )
        + " business setup recommendation",
    )

    module_keys = list(tmpl.modules)
    # Additive modules based on flags
    extras = []
    if flags["inventory_required"] and "INVENTORY" not in module_keys:
        extras.append("INVENTORY")
    if flags["inventory_required"] and "PRODUCTS" not in module_keys:
        extras.append("PRODUCTS")
    if flags["membership_based"] and "MEMBERSHIPS" not in module_keys:
        extras.append("MEMBERSHIPS")
    if flags["equipment_tracking_required"] and "EQUIPMENT" not in module_keys:
        extras.append("EQUIPMENT")
    for key in extras:
        if key in MODULE_BY_KEY:
            module_keys.append(key)

    modules = [
        ModuleRec(
            key=key,
            recommended=True,
            selected=True,
            reason=_module_reason(key, profile),
            confidence="high" if key in tmpl.modules else "medium",
        )
        for key in module_keys
        if key in MODULE_BY_KEY
    ]

    custom_fields: list[CustomFieldRec] = []
    for module_key, defs in (tmpl_data.get("fields") or {}).items():
        for item in defs:
            custom_fields.append(
                CustomFieldRec(
                    name=item.get("label") or item["key"],
                    field_key=item["key"],
                    entity=module_key,
                    reason=f"Common for {profile.industry.replace('_', ' ')} CRM templates.",
                    selected=True,
                )
            )
    for entity, fkey, label in _EXTRA_FIELDS.get(industry, []):
        if any(c.field_key == fkey and c.entity == entity for c in custom_fields):
            continue
        custom_fields.append(
            CustomFieldRec(
                name=label,
                field_key=fkey,
                entity=entity,
                reason=f"Useful for {industry.replace('_', ' ')} service history.",
                selected=True,
            )
        )

    services = [
        ServiceRec(
            name=name,
            description=None,
            reason="Suggested from your industry and description.",
            selected=True,
        )
        for name in _SERVICE_HINTS.get(industry, ())
    ]
    # Mentioned service verbs → ensure AC Repair style entries when HVAC
    if (
        industry == "hvac"
        and "install" in text
        and not any(s.name == "AC Installation" for s in services)
    ):
        services.insert(
            0, ServiceRec(name="AC Installation", reason="Mentioned install work.")
        )

    products = [
        ProductCategoryRec(
            name=name,
            reason="Category suggestion only — no SKUs or prices invented.",
            selected=True,
        )
        for name in _PRODUCT_HINTS.get(industry, ())
        if flags["inventory_required"]
        or "products" in models
        or "products_and_services" in models
    ]

    ai = AiConfigRec(
        recommended=True,
        primary_purpose="CUSTOMER_SERVICE_AND_BOOKING"
        if flags["appointment_based"] or flags["field_service"]
        else "CUSTOMER_SERVICE",
        tone="professional_friendly",
        greeting_suggestion=(
            f"Thanks for calling — how can we help with your "
            f"{industry.replace('_', ' ')} needs today?"
        ),
        capabilities=[
            "answer_business_questions",
            "capture_customer_information",
            "identify_service_needs",
            "book_appointments",
            "reschedule_appointments",
            "create_leads",
            "search_knowledge",
            "transfer_to_human",
        ],
    )

    return SetupRecommendation(
        business_profile=profile,
        modules=modules,
        custom_fields=custom_fields,
        services=services,
        product_categories=products,
        ai_configuration=ai,
        clarifications=clarifications,
        source="heuristic",
    )


def _guess_area(description: str) -> str | None:
    # Lightweight geography hint — not authoritative.
    m = re.search(
        r"\bin\s+([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)?)\b",
        description,
    )
    if m:
        return m.group(1)
    lower = description.lower()
    for state in ("texas", "california", "florida", "new york", "illinois"):
        if state in lower:
            return state.title()
    return None


def recommendation_dict(rec: SetupRecommendation) -> dict[str, Any]:
    return rec.model_dump(mode="json")
