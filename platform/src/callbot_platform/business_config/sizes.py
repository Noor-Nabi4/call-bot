"""Business size catalog."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BusinessSizeDef:
    key: str
    name: str


BUSINESS_SIZES: tuple[BusinessSizeDef, ...] = (
    BusinessSizeDef("solo", "Solo"),
    BusinessSizeDef("small", "Small (2-10)"),
    BusinessSizeDef("medium", "Medium (11-50)"),
    BusinessSizeDef("large", "Large (51-200)"),
    BusinessSizeDef("enterprise", "Enterprise (200+)"),
)

BUSINESS_SIZE_KEYS: frozenset[str] = frozenset(s.key for s in BUSINESS_SIZES)


def list_business_sizes() -> list[dict[str, str]]:
    return [{"key": s.key, "name": s.name} for s in BUSINESS_SIZES]
