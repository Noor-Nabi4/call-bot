"""Canonical industry catalog (machine keys ≠ display names)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class IndustryDef:
    key: str
    name: str
    description: str = ""


INDUSTRIES: tuple[IndustryDef, ...] = (
    IndustryDef("hvac", "HVAC", "Heating, ventilation, and air conditioning"),
    IndustryDef("plumbing", "Plumbing", "Residential and commercial plumbing"),
    IndustryDef("electrical", "Electrical", "Electrical contractors and services"),
    IndustryDef("cleaning", "Cleaning", "Janitorial and cleaning services"),
    IndustryDef("automotive", "Automotive", "Auto repair and service"),
    IndustryDef("dental", "Dental", "Dental practices"),
    IndustryDef("medical", "Medical", "Medical / clinic practices"),
    IndustryDef("real_estate", "Real Estate", "Real estate brokerage and property"),
    IndustryDef("ecommerce", "E-commerce", "Online retail and product commerce"),
    IndustryDef("consulting", "Consulting", "Professional consulting"),
    IndustryDef("beauty_salon", "Beauty / Salon", "Beauty, salon, and spa"),
    IndustryDef("fitness", "Fitness", "Gyms and fitness studios"),
    IndustryDef("custom", "Custom", "Generic / custom business"),
)

INDUSTRY_BY_KEY: dict[str, IndustryDef] = {i.key: i for i in INDUSTRIES}
INDUSTRY_KEYS: frozenset[str] = frozenset(INDUSTRY_BY_KEY)


def list_industries() -> list[dict[str, str]]:
    return [
        {"key": i.key, "name": i.name, "description": i.description} for i in INDUSTRIES
    ]


def normalize_industry_key(raw: str) -> str:
    key = raw.strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "e_commerce": "ecommerce",
        "e-commerce": "ecommerce",
        "beauty": "beauty_salon",
        "salon": "beauty_salon",
        "realestate": "real_estate",
        "hvac_services": "hvac",
    }
    return aliases.get(key, key)
