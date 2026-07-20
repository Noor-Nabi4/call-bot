"""SaaS billing package (platform Stripe subscriptions)."""

from __future__ import annotations

from typing import Any

__all__ = ["BillingError", "BillingService"]


def __getattr__(name: str) -> Any:
    if name == "BillingError":
        from callbot_platform.billing.errors import BillingError

        return BillingError
    if name == "BillingService":
        from callbot_platform.billing.service import BillingService

        return BillingService
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
