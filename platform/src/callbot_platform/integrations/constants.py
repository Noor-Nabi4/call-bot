"""Phase 28 integration constants."""

from __future__ import annotations

from enum import Enum


class IntegrationCategory(str, Enum):
    CRM = "crm"
    CALENDAR = "calendar"
    COMMERCE = "commerce"
    ACCOUNTING = "accounting"


class IntegrationStatus(str, Enum):
    DISCONNECTED = "DISCONNECTED"
    CONNECTING = "CONNECTING"
    CONNECTED = "CONNECTED"
    SYNCING = "SYNCING"
    SYNCED = "SYNCED"
    ERROR = "ERROR"
    REAUTH_REQUIRED = "REAUTH_REQUIRED"
    DISABLED = "DISABLED"


class SyncDirection(str, Enum):
    IMPORT = "IMPORT"
    EXPORT = "EXPORT"
    BIDIRECTIONAL = "BIDIRECTIONAL"


class SyncRunStatus(str, Enum):
    PENDING = "PENDING"
    RUNNING = "RUNNING"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"


class HealthStatus(str, Enum):
    HEALTHY = "HEALTHY"
    AUTH_REQUIRED = "AUTH_REQUIRED"
    NOT_CONFIGURED = "NOT_CONFIGURED"
    RATE_LIMITED = "RATE_LIMITED"
    UNAVAILABLE = "UNAVAILABLE"
    ERROR = "ERROR"


class Capability(str, Enum):
    CUSTOMERS_READ = "CUSTOMERS_READ"
    CUSTOMERS_WRITE = "CUSTOMERS_WRITE"
    LEADS_READ = "LEADS_READ"
    LEADS_WRITE = "LEADS_WRITE"
    APPOINTMENTS_READ = "APPOINTMENTS_READ"
    APPOINTMENTS_WRITE = "APPOINTMENTS_WRITE"
    PRODUCTS_READ = "PRODUCTS_READ"
    ORDERS_READ = "ORDERS_READ"
    INVOICES_READ = "INVOICES_READ"
    INVOICES_WRITE = "INVOICES_WRITE"
    PAYMENTS_READ = "PAYMENTS_READ"
    WEBHOOKS = "WEBHOOKS"
    BIDIRECTIONAL_SYNC = "BIDIRECTIONAL_SYNC"
    OAUTH = "OAUTH"


class ProviderKey(str, Enum):
    SERVICETITAN = "servicetitan"
    HUBSPOT = "hubspot"
    SALESFORCE = "salesforce"
    GOOGLE_CALENDAR = "google_calendar"
    OUTLOOK_CALENDAR = "outlook_calendar"
    SHOPIFY = "shopify"
    WOOCOMMERCE = "woocommerce"
    QUICKBOOKS = "quickbooks"
    XERO = "xero"


PROVIDER_KEYS: frozenset[str] = frozenset(p.value for p in ProviderKey)
OAUTH_STATE_TTL_SECONDS = 600
MAX_SYNC_RETRIES = 5
