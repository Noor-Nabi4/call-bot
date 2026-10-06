"""Services & Pricebook facade (Phase 7)."""

from __future__ import annotations

from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.crm.services.catalog import ServiceCatalogOps
from callbot_platform.crm.services.categories import ServiceCategoryService
from callbot_platform.crm.services.pricebooks import PricebookService
from callbot_platform.crm.services.pricing import PricingService
from callbot_platform.crm.services.search import ServiceSearchService


class ServicesPricebookService:
    """Unified entry point for services, categories, pricebooks, and pricing."""

    def __init__(self, session: Session) -> None:
        self._session = session
        self.categories = ServiceCategoryService(session)
        self.catalog = ServiceCatalogOps(session)
        self.search = ServiceSearchService(session)
        self.pricebooks = PricebookService(session)
        self.pricing = PricingService(session)

    def list_services(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.search.search(tenant_id, **kwargs)

    def get_service(
        self, tenant_id: UUID, service_id: UUID, **kwargs: Any
    ) -> dict[str, Any]:
        return self.catalog.get(tenant_id, service_id, **kwargs)

    def create_service(self, tenant_id: UUID, **kwargs: Any) -> dict[str, Any]:
        return self.catalog.create(tenant_id, **kwargs)

    def update_service(
        self, tenant_id: UUID, service_id: UUID, **kwargs: Any
    ) -> dict[str, Any]:
        return self.catalog.update(tenant_id, service_id, **kwargs)

    def archive_service(
        self, tenant_id: UUID, service_id: UUID, **kwargs: Any
    ) -> dict[str, Any]:
        return self.catalog.archive(tenant_id, service_id, **kwargs)

    def restore_service(
        self, tenant_id: UUID, service_id: UUID, **kwargs: Any
    ) -> dict[str, Any]:
        return self.catalog.restore(tenant_id, service_id, **kwargs)

    def resolve_price(
        self,
        tenant_id: UUID,
        *,
        service_id: UUID,
        pricebook_id: UUID | None = None,
        at: datetime | None = None,
    ) -> dict[str, Any]:
        return self.pricing.resolve_service_price(
            tenant_id,
            service_id=service_id,
            pricebook_id=pricebook_id,
            at=at,
        )


__all__ = ["ServicesPricebookService"]
