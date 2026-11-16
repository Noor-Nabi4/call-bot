"""Provider capability catalog — UI and sync must respect declared capabilities."""

from __future__ import annotations

from callbot_platform.integrations.constants import (
    Capability,
    IntegrationCategory,
    ProviderKey,
)
from callbot_platform.integrations.protocols import ProviderDescriptor

C = Capability

PROVIDER_CATALOG: dict[str, ProviderDescriptor] = {
    ProviderKey.SERVICETITAN.value: ProviderDescriptor(
        key=ProviderKey.SERVICETITAN.value,
        name="ServiceTitan",
        category=IntegrationCategory.CRM,
        description="Field service CRM sync for customers, jobs, and appointments.",
        capabilities=frozenset(
            {
                C.CUSTOMERS_READ,
                C.CUSTOMERS_WRITE,
                C.APPOINTMENTS_READ,
                C.APPOINTMENTS_WRITE,
                C.BIDIRECTIONAL_SYNC,
            }
        ),
        oauth=False,
        default_sync_direction="BIDIRECTIONAL",
    ),
    ProviderKey.HUBSPOT.value: ProviderDescriptor(
        key=ProviderKey.HUBSPOT.value,
        name="HubSpot",
        category=IntegrationCategory.CRM,
        description="CRM contacts and leads synchronization.",
        capabilities=frozenset(
            {C.CUSTOMERS_READ, C.CUSTOMERS_WRITE, C.LEADS_READ, C.LEADS_WRITE, C.OAUTH}
        ),
    ),
    ProviderKey.SALESFORCE.value: ProviderDescriptor(
        key=ProviderKey.SALESFORCE.value,
        name="Salesforce",
        category=IntegrationCategory.CRM,
        description="Enterprise CRM accounts, contacts, and leads.",
        capabilities=frozenset(
            {C.CUSTOMERS_READ, C.CUSTOMERS_WRITE, C.LEADS_READ, C.LEADS_WRITE, C.OAUTH}
        ),
    ),
    ProviderKey.GOOGLE_CALENDAR.value: ProviderDescriptor(
        key=ProviderKey.GOOGLE_CALENDAR.value,
        name="Google Calendar",
        category=IntegrationCategory.CALENDAR,
        description="Sync appointments with Google Calendar.",
        capabilities=frozenset(
            {
                C.APPOINTMENTS_READ,
                C.APPOINTMENTS_WRITE,
                C.OAUTH,
                C.WEBHOOKS,
                C.BIDIRECTIONAL_SYNC,
            }
        ),
        default_sync_direction="BIDIRECTIONAL",
    ),
    ProviderKey.OUTLOOK_CALENDAR.value: ProviderDescriptor(
        key=ProviderKey.OUTLOOK_CALENDAR.value,
        name="Outlook Calendar",
        category=IntegrationCategory.CALENDAR,
        description="Sync appointments with Microsoft Outlook / Graph.",
        capabilities=frozenset(
            {
                C.APPOINTMENTS_READ,
                C.APPOINTMENTS_WRITE,
                C.OAUTH,
                C.WEBHOOKS,
                C.BIDIRECTIONAL_SYNC,
            }
        ),
        default_sync_direction="BIDIRECTIONAL",
    ),
    ProviderKey.SHOPIFY.value: ProviderDescriptor(
        key=ProviderKey.SHOPIFY.value,
        name="Shopify",
        category=IntegrationCategory.COMMERCE,
        description="Import products and orders from Shopify.",
        capabilities=frozenset(
            {C.PRODUCTS_READ, C.ORDERS_READ, C.CUSTOMERS_READ, C.OAUTH, C.WEBHOOKS}
        ),
    ),
    ProviderKey.WOOCOMMERCE.value: ProviderDescriptor(
        key=ProviderKey.WOOCOMMERCE.value,
        name="WooCommerce",
        category=IntegrationCategory.COMMERCE,
        description="Import products and orders from WooCommerce.",
        capabilities=frozenset(
            {C.PRODUCTS_READ, C.ORDERS_READ, C.CUSTOMERS_READ, C.WEBHOOKS}
        ),
        oauth=False,
    ),
    ProviderKey.QUICKBOOKS.value: ProviderDescriptor(
        key=ProviderKey.QUICKBOOKS.value,
        name="QuickBooks",
        category=IntegrationCategory.ACCOUNTING,
        description="Sync customers, invoices, and payments with QuickBooks Online.",
        capabilities=frozenset(
            {
                C.CUSTOMERS_READ,
                C.CUSTOMERS_WRITE,
                C.INVOICES_READ,
                C.INVOICES_WRITE,
                C.PAYMENTS_READ,
                C.OAUTH,
            }
        ),
    ),
    ProviderKey.XERO.value: ProviderDescriptor(
        key=ProviderKey.XERO.value,
        name="Xero",
        category=IntegrationCategory.ACCOUNTING,
        description="Sync contacts, invoices, and payments with Xero.",
        capabilities=frozenset(
            {
                C.CUSTOMERS_READ,
                C.CUSTOMERS_WRITE,
                C.INVOICES_READ,
                C.INVOICES_WRITE,
                C.PAYMENTS_READ,
                C.OAUTH,
            }
        ),
    ),
}


def list_catalog() -> list[ProviderDescriptor]:
    return list(PROVIDER_CATALOG.values())


def get_descriptor(provider: str) -> ProviderDescriptor | None:
    return PROVIDER_CATALOG.get(provider)
