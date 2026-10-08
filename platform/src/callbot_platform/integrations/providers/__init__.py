"""Provider adapters — Call & Flow core never imports these directly outside registry."""

from __future__ import annotations

from callbot_platform.integrations.providers.accounting import (
    QuickBooksAdapter,
    XeroAdapter,
)
from callbot_platform.integrations.providers.base import BaseProviderAdapter
from callbot_platform.integrations.providers.calendar import (
    GoogleCalendarAdapter,
    OutlookCalendarAdapter,
)
from callbot_platform.integrations.providers.commerce import (
    ShopifyAdapter,
    WooCommerceAdapter,
)
from callbot_platform.integrations.providers.crm import (
    HubSpotAdapter,
    SalesforceAdapter,
    ServiceTitanAdapter,
)


def build_provider_registry() -> dict[str, BaseProviderAdapter]:
    adapters: list[BaseProviderAdapter] = [
        GoogleCalendarAdapter(),
        OutlookCalendarAdapter(),
        HubSpotAdapter(),
        SalesforceAdapter(),
        ServiceTitanAdapter(),
        ShopifyAdapter(),
        WooCommerceAdapter(),
        QuickBooksAdapter(),
        XeroAdapter(),
    ]
    return {a.descriptor.key: a for a in adapters}


__all__ = [
    "BaseProviderAdapter",
    "GoogleCalendarAdapter",
    "HubSpotAdapter",
    "OutlookCalendarAdapter",
    "QuickBooksAdapter",
    "SalesforceAdapter",
    "ServiceTitanAdapter",
    "ShopifyAdapter",
    "WooCommerceAdapter",
    "XeroAdapter",
    "build_provider_registry",
]
