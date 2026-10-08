"""CRM provider adapters (ServiceTitan, HubSpot, Salesforce)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from callbot_platform.integrations.catalog import PROVIDER_CATALOG
from callbot_platform.integrations.constants import HealthStatus, ProviderKey
from callbot_platform.integrations.errors import IntegrationError
from callbot_platform.integrations.http import request_with_retry
from callbot_platform.integrations.protocols import (
    ExternalCustomer,
    ExternalLead,
    HealthResult,
    SyncPage,
)
from callbot_platform.integrations.providers.base import BaseProviderAdapter


class HubSpotAdapter(BaseProviderAdapter):
    def __init__(self) -> None:
        self.descriptor = PROVIDER_CATALOG[ProviderKey.HUBSPOT.value]

    def health_check(self, *, credentials: dict[str, Any] | None) -> HealthResult:
        base = super().health_check(credentials=credentials)
        if base.status != HealthStatus.HEALTHY:
            return base
        token = (credentials or {}).get("access_token")
        if not token:
            return HealthResult(
                status=HealthStatus.AUTH_REQUIRED, message="HubSpot token missing"
            )
        try:
            request_with_retry(
                "GET",
                "https://api.hubapi.com/crm/v3/objects/contacts",
                headers={"Authorization": f"Bearer {token}"},
                params={"limit": "1"},
                max_retries=1,
            )
        except IntegrationError as exc:
            return HealthResult(status=HealthStatus.ERROR, message=exc.message)
        return HealthResult(status=HealthStatus.HEALTHY, message="HubSpot OK")

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
        params: dict[str, Any] = {"limit": 50}
        if cursor:
            params["after"] = cursor
        try:
            response = request_with_retry(
                "GET",
                "https://api.hubapi.com/crm/v3/objects/contacts",
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
                params=params,
                max_retries=2,
            )
        except IntegrationError:
            return SyncPage(items=[], done=True)
        data = response.json()
        results = data.get("results") or []
        items = [
            ExternalCustomer(
                external_id=str(r["id"]),
                name=_hubspot_name(r.get("properties") or {}),
                email=(r.get("properties") or {}).get("email"),
                phone=(r.get("properties") or {}).get("phone"),
                raw={"provider": "hubspot"},
            )
            for r in results
            if isinstance(r, dict) and r.get("id")
        ]
        next_after = (data.get("paging") or {}).get("next", {}).get("after")
        return SyncPage(items=items, next_cursor=next_after, done=not bool(next_after))


class SalesforceAdapter(BaseProviderAdapter):
    def __init__(self) -> None:
        self.descriptor = PROVIDER_CATALOG[ProviderKey.SALESFORCE.value]

    def health_check(self, *, credentials: dict[str, Any] | None) -> HealthResult:
        base = super().health_check(credentials=credentials)
        if base.status != HealthStatus.HEALTHY:
            return base
        instance = (credentials or {}).get("extra", {}).get("instance_url")
        if not instance:
            return HealthResult(
                status=HealthStatus.AUTH_REQUIRED,
                message="Salesforce instance URL missing",
            )
        return HealthResult(
            status=HealthStatus.HEALTHY,
            message="Credentials present (live Salesforce probe gated on sandbox)",
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
        instance = (credentials.get("extra") or {}).get("instance_url")
        if not instance:
            return SyncPage(items=[], done=True)
        url = cursor or (
            f"{instance}/services/data/v59.0/query"
            "?q=SELECT+Id,Name,Email,Phone+FROM+Contact+LIMIT+50"
        )
        try:
            response = request_with_retry(
                "GET",
                url,
                headers={"Authorization": f"Bearer {credentials['access_token']}"},
                max_retries=2,
            )
        except IntegrationError:
            return SyncPage(items=[], done=True)
        data = response.json()
        records = data.get("records") or []
        items = [
            ExternalCustomer(
                external_id=str(r["Id"]),
                name=r.get("Name"),
                email=r.get("Email"),
                phone=r.get("Phone"),
                raw={"provider": "salesforce"},
            )
            for r in records
            if isinstance(r, dict) and r.get("Id")
        ]
        next_url = data.get("nextRecordsUrl")
        next_cursor = f"{instance}{next_url}" if next_url else None
        return SyncPage(
            items=items, next_cursor=next_cursor, done=not bool(next_cursor)
        )


class ServiceTitanAdapter(BaseProviderAdapter):
    """ServiceTitan uses app-key + client credentials (stored encrypted)."""

    def __init__(self) -> None:
        self.descriptor = PROVIDER_CATALOG[ProviderKey.SERVICETITAN.value]

    def health_check(self, *, credentials: dict[str, Any] | None) -> HealthResult:
        extra = (credentials or {}).get("extra") or {}
        if not extra.get("client_id") and not (credentials or {}).get(
            "has_access_token"
        ):
            return HealthResult(
                status=HealthStatus.AUTH_REQUIRED,
                message="ServiceTitan credentials not connected",
            )
        return HealthResult(
            status=HealthStatus.HEALTHY,
            message="Credentials present (live ServiceTitan probe gated on sandbox)",
        )

    def sync_page(
        self,
        *,
        tenant_id: UUID,
        credentials: dict[str, Any] | None,
        cursor: str | None,
        direction: str,
    ) -> SyncPage:
        _ = (tenant_id, credentials, cursor, direction)
        # Live ST API requires tenant-specific base URL + app key — verification blocked.
        return SyncPage(items=[], done=True)

    def normalize_lead(self, payload: dict[str, Any]) -> ExternalLead:
        return ExternalLead(
            external_id=str(payload.get("id") or payload.get("leadId") or ""),
            title=payload.get("summary") or payload.get("title"),
            email=payload.get("email"),
            phone=payload.get("phone"),
            status=payload.get("status"),
            raw={"provider": "servicetitan"},
        )


def _hubspot_name(props: dict[str, Any]) -> str | None:
    first = props.get("firstname") or ""
    last = props.get("lastname") or ""
    name = f"{first} {last}".strip()
    return name or None
