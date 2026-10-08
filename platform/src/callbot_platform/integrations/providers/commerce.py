"""Commerce provider adapters (Shopify + WooCommerce)."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from callbot_platform.integrations.catalog import PROVIDER_CATALOG
from callbot_platform.integrations.constants import HealthStatus, ProviderKey
from callbot_platform.integrations.errors import IntegrationError
from callbot_platform.integrations.http import request_with_retry
from callbot_platform.integrations.protocols import (
    ExternalOrder,
    ExternalProduct,
    HealthResult,
    SyncPage,
)
from callbot_platform.integrations.providers.base import BaseProviderAdapter


class ShopifyAdapter(BaseProviderAdapter):
    def __init__(self) -> None:
        self.descriptor = PROVIDER_CATALOG[ProviderKey.SHOPIFY.value]

    def health_check(self, *, credentials: dict[str, Any] | None) -> HealthResult:
        base = super().health_check(credentials=credentials)
        if base.status != HealthStatus.HEALTHY:
            return base
        shop = (credentials or {}).get("extra", {}).get("shop")
        token = (credentials or {}).get("access_token")
        if not shop or not token:
            return HealthResult(
                status=HealthStatus.AUTH_REQUIRED,
                message="Shopify shop or access token missing",
            )
        try:
            request_with_retry(
                "GET",
                f"https://{shop}/admin/api/2024-10/shop.json",
                headers={"X-Shopify-Access-Token": str(token)},
                max_retries=1,
            )
        except IntegrationError as exc:
            return HealthResult(status=HealthStatus.ERROR, message=exc.message)
        return HealthResult(status=HealthStatus.HEALTHY, message="Shopify OK")

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
        shop = (credentials.get("extra") or {}).get("shop")
        if not shop:
            return SyncPage(items=[], done=True)
        token = str(credentials["access_token"])
        url = cursor or f"https://{shop}/admin/api/2024-10/products.json?limit=50"
        try:
            response = request_with_retry(
                "GET",
                url,
                headers={"X-Shopify-Access-Token": token},
                max_retries=2,
            )
        except IntegrationError:
            return SyncPage(items=[], done=True)
        products = response.json().get("products") or []
        items = [
            ExternalProduct(
                external_id=str(p["id"]),
                name=p.get("title"),
                sku=(p.get("variants") or [{}])[0].get("sku"),
                price=_float((p.get("variants") or [{}])[0].get("price")),
                raw={"provider": "shopify"},
            )
            for p in products
            if isinstance(p, dict) and p.get("id")
        ]
        # Shopify cursor pagination via Link header is adapter-specific; done after page.
        return SyncPage(items=items, next_cursor=None, done=True)

    def sync_orders_page(
        self, *, credentials: dict[str, Any] | None, cursor: str | None = None
    ) -> SyncPage:
        if not credentials or not credentials.get("access_token"):
            return SyncPage(items=[], done=True)
        shop = (credentials.get("extra") or {}).get("shop")
        if not shop:
            return SyncPage(items=[], done=True)
        url = (
            cursor
            or f"https://{shop}/admin/api/2024-10/orders.json?limit=50&status=any"
        )
        response = request_with_retry(
            "GET",
            url,
            headers={"X-Shopify-Access-Token": str(credentials["access_token"])},
            max_retries=2,
        )
        orders = response.json().get("orders") or []
        items = [
            ExternalOrder(
                external_id=str(o["id"]),
                order_number=str(o.get("name") or o.get("order_number") or ""),
                status=o.get("financial_status"),
                total=_float(o.get("total_price")),
                currency=o.get("currency"),
                raw={"provider": "shopify"},
            )
            for o in orders
            if isinstance(o, dict) and o.get("id")
        ]
        return SyncPage(items=items, next_cursor=None, done=True)


class WooCommerceAdapter(BaseProviderAdapter):
    def __init__(self) -> None:
        self.descriptor = PROVIDER_CATALOG[ProviderKey.WOOCOMMERCE.value]

    def health_check(self, *, credentials: dict[str, Any] | None) -> HealthResult:
        extra = (credentials or {}).get("extra") or {}
        if not extra.get("consumer_key") or not extra.get("store_url"):
            return HealthResult(
                status=HealthStatus.AUTH_REQUIRED,
                message="WooCommerce API credentials not connected",
            )
        return HealthResult(
            status=HealthStatus.HEALTHY,
            message="Credentials present (live WooCommerce probe gated on store URL)",
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
        extra = (credentials or {}).get("extra") or {}
        store = (extra.get("store_url") or "").rstrip("/")
        key = extra.get("consumer_key")
        secret = extra.get("consumer_secret")
        if not store or not key or not secret:
            return SyncPage(items=[], done=True)
        page = int(cursor or "1")
        try:
            response = request_with_retry(
                "GET",
                f"{store}/wp-json/wc/v3/products",
                params={
                    "consumer_key": key,
                    "consumer_secret": secret,
                    "page": page,
                    "per_page": 50,
                },
                max_retries=2,
            )
        except IntegrationError:
            return SyncPage(items=[], done=True)
        products = response.json()
        if not isinstance(products, list):
            return SyncPage(items=[], done=True)
        items = [
            ExternalProduct(
                external_id=str(p["id"]),
                name=p.get("name"),
                sku=p.get("sku"),
                price=_float(p.get("price")),
                raw={"provider": "woocommerce"},
            )
            for p in products
            if isinstance(p, dict) and p.get("id")
        ]
        next_cursor = str(page + 1) if len(items) >= 50 else None
        return SyncPage(items=items, next_cursor=next_cursor, done=next_cursor is None)


def _float(value: Any) -> float | None:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None
