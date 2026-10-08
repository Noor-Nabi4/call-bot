"""Accounting provider adapters (QuickBooks + Xero)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from callbot_platform.integrations.catalog import PROVIDER_CATALOG
from callbot_platform.integrations.constants import HealthStatus, ProviderKey
from callbot_platform.integrations.errors import IntegrationError
from callbot_platform.integrations.http import request_with_retry
from callbot_platform.integrations.protocols import (
    ExternalCustomer,
    ExternalInvoice,
    HealthResult,
    SyncPage,
)
from callbot_platform.integrations.providers.base import BaseProviderAdapter


class QuickBooksAdapter(BaseProviderAdapter):
    def __init__(self) -> None:
        self.descriptor = PROVIDER_CATALOG[ProviderKey.QUICKBOOKS.value]

    def health_check(self, *, credentials: dict[str, Any] | None) -> HealthResult:
        base = super().health_check(credentials=credentials)
        if base.status != HealthStatus.HEALTHY:
            return base
        realm = (credentials or {}).get("extra", {}).get("realm_id") or (
            credentials or {}
        ).get("external_account_id")
        if not realm:
            return HealthResult(
                status=HealthStatus.AUTH_REQUIRED,
                message="QuickBooks company (realm) not connected",
            )
        return HealthResult(
            status=HealthStatus.HEALTHY,
            message="Credentials present (live QBO probe gated on sandbox)",
        )

    def sync_page(
        self,
        *,
        tenant_id: UUID,
        credentials: dict[str, Any] | None,
        cursor: str | None,
        direction: str,
    ) -> SyncPage:
        _ = (tenant_id, direction)
        if not credentials or not credentials.get("access_token"):
            return SyncPage(items=[], done=True)
        realm = (credentials.get("extra") or {}).get("realm_id")
        if not realm:
            return SyncPage(items=[], done=True)
        start = int(cursor or "1")
        query = f"select * from Customer startposition {start} maxresults 50"
        try:
            response = request_with_retry(
                "GET",
                f"https://quickbooks.api.intuit.com/v3/company/{realm}/query",
                headers={
                    "Authorization": f"Bearer {credentials['access_token']}",
                    "Accept": "application/json",
                },
                params={"query": query},
                max_retries=2,
            )
        except IntegrationError:
            return SyncPage(items=[], done=True)
        customers = (response.json().get("QueryResponse") or {}).get("Customer") or []
        items = [
            ExternalCustomer(
                external_id=str(c["Id"]),
                name=c.get("DisplayName"),
                email=((c.get("PrimaryEmailAddr") or {}).get("Address")),
                phone=((c.get("PrimaryPhone") or {}).get("FreeFormNumber")),
                raw={"provider": "quickbooks"},
            )
            for c in customers
            if isinstance(c, dict) and c.get("Id")
        ]
        next_cursor = str(start + 50) if len(items) >= 50 else None
        return SyncPage(items=items, next_cursor=next_cursor, done=next_cursor is None)


class XeroAdapter(BaseProviderAdapter):
    def __init__(self) -> None:
        self.descriptor = PROVIDER_CATALOG[ProviderKey.XERO.value]

    def health_check(self, *, credentials: dict[str, Any] | None) -> HealthResult:
        base = super().health_check(credentials=credentials)
        if base.status != HealthStatus.HEALTHY:
            return base
        tenant_xero = (credentials or {}).get("extra", {}).get("xero_tenant_id")
        if not tenant_xero:
            return HealthResult(
                status=HealthStatus.AUTH_REQUIRED,
                message="Xero organization tenant not selected",
            )
        return HealthResult(
            status=HealthStatus.HEALTHY,
            message="Credentials present (live Xero probe gated on sandbox)",
        )

    def sync_page(
        self,
        *,
        tenant_id: UUID,
        credentials: dict[str, Any] | None,
        cursor: str | None,
        direction: str,
    ) -> SyncPage:
        _ = (tenant_id, direction, cursor)
        if not credentials or not credentials.get("access_token"):
            return SyncPage(items=[], done=True)
        xero_tenant = (credentials.get("extra") or {}).get("xero_tenant_id")
        if not xero_tenant:
            return SyncPage(items=[], done=True)
        try:
            response = request_with_retry(
                "GET",
                "https://api.xero.com/api.xro/2.0/Contacts",
                headers={
                    "Authorization": f"Bearer {credentials['access_token']}",
                    "Xero-Tenant-Id": str(xero_tenant),
                    "Accept": "application/json",
                },
                max_retries=2,
            )
        except IntegrationError:
            return SyncPage(items=[], done=True)
        contacts = response.json().get("Contacts") or []
        items = [
            ExternalCustomer(
                external_id=str(c["ContactID"]),
                name=c.get("Name"),
                email=c.get("EmailAddress"),
                phone=_xero_phone(c),
                raw={"provider": "xero"},
            )
            for c in contacts
            if isinstance(c, dict) and c.get("ContactID")
        ]
        return SyncPage(items=items, next_cursor=None, done=True)

    def sync_invoices(
        self, *, credentials: dict[str, Any] | None
    ) -> list[ExternalInvoice]:
        if not credentials or not credentials.get("access_token"):
            return []
        xero_tenant = (credentials.get("extra") or {}).get("xero_tenant_id")
        if not xero_tenant:
            return []
        response = request_with_retry(
            "GET",
            "https://api.xero.com/api.xro/2.0/Invoices",
            headers={
                "Authorization": f"Bearer {credentials['access_token']}",
                "Xero-Tenant-Id": str(xero_tenant),
                "Accept": "application/json",
            },
            max_retries=2,
        )
        invoices = response.json().get("Invoices") or []
        return [
            ExternalInvoice(
                external_id=str(i["InvoiceID"]),
                invoice_number=i.get("InvoiceNumber"),
                status=i.get("Status"),
                total=_float(i.get("Total")),
                balance_due=_float(i.get("AmountDue")),
                raw={"provider": "xero"},
            )
            for i in invoices
            if isinstance(i, dict) and i.get("InvoiceID")
        ]


def _xero_phone(contact: dict[str, Any]) -> str | None:
    phones = contact.get("Phones") or []
    for phone in phones:
        if isinstance(phone, dict) and phone.get("PhoneNumber"):
            return str(phone["PhoneNumber"])
    return None


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
