"""Provider registry/factory — resolve adapters by provider key."""

from __future__ import annotations

from callbot_platform.integrations.errors import IntegrationError
from callbot_platform.integrations.providers import build_provider_registry
from callbot_platform.integrations.providers.base import BaseProviderAdapter

_REGISTRY: dict[str, BaseProviderAdapter] | None = None


def get_registry() -> dict[str, BaseProviderAdapter]:
    global _REGISTRY
    if _REGISTRY is None:
        _REGISTRY = build_provider_registry()
    return _REGISTRY


def get_provider(provider: str) -> BaseProviderAdapter:
    reg = get_registry()
    adapter = reg.get(provider)
    if adapter is None:
        raise IntegrationError("UNKNOWN_PROVIDER", f"Unknown provider: {provider}")
    return adapter
