"""Service catalog CRUD."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.services.constants import DEFAULT_PRICING_TYPE, DEFAULT_STATUS
from callbot_platform.crm.services.normalize import (
    normalize_code,
    normalize_pricing_type,
    normalize_status,
    parse_money,
    parse_tax_rate,
    trim,
)
from callbot_platform.crm.services.serialize import serialize_service
from callbot_platform.db.models.services import Service, ServiceCategory
from callbot_platform.telephony.audit import write_audit


class ServiceCatalogOps:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(
        self,
        tenant_id: UUID,
        service_id: UUID,
        *,
        include_archived: bool = True,
        include_cost: bool = True,
    ) -> dict[str, Any]:
        row = self._load(tenant_id, service_id, require_active=not include_archived)
        return serialize_service(
            row,
            category_name=self._category_name(tenant_id, row.category_id),
            include_cost=include_cost,
        )

    def create(
        self,
        tenant_id: UUID,
        *,
        name: str,
        code: str | None = None,
        description: str | None = None,
        category_id: UUID | None = None,
        duration_minutes: int | None = None,
        base_price: object | None = None,
        cost: object | None = None,
        tax_rate: object | None = None,
        pricing_type: str | None = None,
        status: str | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        cleaned_name = trim(name, max_len=255, field="name")
        if not cleaned_name:
            raise CrmError("invalid_name", "Service name is required")
        display_code, code_norm = normalize_code(code)
        category = self._resolve_category(tenant_id, category_id)
        duration = self._parse_duration(duration_minutes)
        row = Service(
            tenant_id=tenant_id,
            name=cleaned_name,
            code=display_code,
            code_normalized=code_norm,
            description=trim(description, max_len=20000, field="description"),
            category_id=category.id if category else None,
            duration_minutes=duration,
            base_price=parse_money(base_price, field="base_price"),
            cost=parse_money(cost, field="cost"),
            tax_rate=parse_tax_rate(tax_rate),
            pricing_type=normalize_pricing_type(
                pricing_type, default=DEFAULT_PRICING_TYPE
            ),
            status=normalize_status(status, default=DEFAULT_STATUS),
            created_by=actor,
            updated_by=actor,
        )
        if code_norm:
            self._assert_code_available(tenant_id, code_norm)
        self._session.add(row)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "code_conflict", "Service code already in use for this tenant"
            ) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="service_created",
            resource_ids={"service_id": str(row.id)},
        )
        return serialize_service(
            row,
            category_name=category.name if category else None,
            include_cost=True,
        )

    def update(
        self,
        tenant_id: UUID,
        service_id: UUID,
        *,
        name: str | None = None,
        code: str | None = None,
        clear_code: bool = False,
        description: str | None = None,
        category_id: UUID | None = None,
        clear_category: bool = False,
        duration_minutes: int | None = None,
        clear_duration: bool = False,
        base_price: object | None = None,
        clear_base_price: bool = False,
        cost: object | None = None,
        clear_cost: bool = False,
        tax_rate: object | None = None,
        clear_tax_rate: bool = False,
        pricing_type: str | None = None,
        status: str | None = None,
        actor: str = "system",
    ) -> dict[str, Any]:
        row = self._load(tenant_id, service_id, require_active=False)
        if row.archived_at is not None:
            raise CrmError("service_archived", "Cannot update an archived service")
        if name is not None:
            cleaned = trim(name, max_len=255, field="name")
            if not cleaned:
                raise CrmError("invalid_name", "Service name is required")
            row.name = cleaned
        if clear_code:
            row.code = None
            row.code_normalized = None
        elif code is not None:
            display_code, code_norm = normalize_code(code)
            if code_norm:
                self._assert_code_available(tenant_id, code_norm, exclude_id=row.id)
            row.code = display_code
            row.code_normalized = code_norm
        if description is not None:
            row.description = trim(description, max_len=20000, field="description")
        if clear_category:
            row.category_id = None
        elif category_id is not None:
            category = self._resolve_category(tenant_id, category_id)
            row.category_id = category.id if category else None
        if clear_duration:
            row.duration_minutes = None
        elif duration_minutes is not None:
            row.duration_minutes = self._parse_duration(duration_minutes)
        if clear_base_price:
            row.base_price = None
        elif base_price is not None:
            row.base_price = parse_money(base_price, field="base_price")
        if clear_cost:
            row.cost = None
        elif cost is not None:
            row.cost = parse_money(cost, field="cost")
        if clear_tax_rate:
            row.tax_rate = None
        elif tax_rate is not None:
            row.tax_rate = parse_tax_rate(tax_rate)
        if pricing_type is not None:
            row.pricing_type = normalize_pricing_type(pricing_type)
        if status is not None:
            row.status = normalize_status(status)
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        try:
            self._session.flush()
        except IntegrityError as exc:
            raise CrmError(
                "code_conflict", "Service code already in use for this tenant"
            ) from exc
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="service_updated",
            resource_ids={"service_id": str(row.id)},
        )
        return serialize_service(
            row,
            category_name=self._category_name(tenant_id, row.category_id),
            include_cost=True,
        )

    def archive(
        self, tenant_id: UUID, service_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any]:
        row = self._load(tenant_id, service_id, require_active=True)
        row.archived_at = datetime.now(UTC)
        row.status = "INACTIVE"
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="service_archived",
            resource_ids={"service_id": str(row.id)},
        )
        return serialize_service(
            row,
            category_name=self._category_name(tenant_id, row.category_id),
            include_cost=True,
        )

    def restore(
        self, tenant_id: UUID, service_id: UUID, *, actor: str = "system"
    ) -> dict[str, Any]:
        row = self._load(tenant_id, service_id, require_active=False)
        if row.archived_at is None:
            return serialize_service(
                row,
                category_name=self._category_name(tenant_id, row.category_id),
                include_cost=True,
            )
        if row.category_id is not None:
            cat = self._session.scalar(
                select(ServiceCategory).where(
                    ServiceCategory.id == row.category_id,
                    ServiceCategory.tenant_id == tenant_id,
                )
            )
            if cat is None or cat.archived_at is not None:
                raise CrmError(
                    "invalid_category",
                    "Cannot restore service under an archived or missing category",
                )
        if row.code_normalized:
            conflict = self._session.scalar(
                select(Service.id).where(
                    Service.tenant_id == tenant_id,
                    Service.code_normalized == row.code_normalized,
                    Service.archived_at.is_(None),
                    Service.id != row.id,
                )
            )
            if conflict is not None:
                raise CrmError(
                    "code_conflict",
                    "Another active service already uses this code",
                )
        row.archived_at = None
        row.status = DEFAULT_STATUS
        row.updated_by = actor
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="service_restored",
            resource_ids={"service_id": str(row.id)},
        )
        return serialize_service(
            row,
            category_name=self._category_name(tenant_id, row.category_id),
            include_cost=True,
        )

    def _assert_code_available(
        self,
        tenant_id: UUID,
        code_normalized: str,
        *,
        exclude_id: UUID | None = None,
    ) -> None:
        q = select(Service.id).where(
            Service.tenant_id == tenant_id,
            Service.code_normalized == code_normalized,
            Service.archived_at.is_(None),
        )
        if exclude_id is not None:
            q = q.where(Service.id != exclude_id)
        if self._session.scalar(q) is not None:
            raise CrmError(
                "code_conflict", "Service code already in use for this tenant"
            )

    def _load(
        self, tenant_id: UUID, service_id: UUID, *, require_active: bool
    ) -> Service:
        row = self._session.scalar(
            select(Service).where(
                Service.id == service_id,
                Service.tenant_id == tenant_id,
            )
        )
        if row is None:
            raise CrmError("not_found", "Service not found for tenant")
        if require_active and row.archived_at is not None:
            raise CrmError("not_found", "Service not found for tenant")
        return row

    def _resolve_category(
        self, tenant_id: UUID, category_id: UUID | None
    ) -> ServiceCategory | None:
        if category_id is None:
            return None
        cat = self._session.scalar(
            select(ServiceCategory).where(
                ServiceCategory.id == category_id,
                ServiceCategory.tenant_id == tenant_id,
            )
        )
        if cat is None:
            raise CrmError("invalid_category", "Category not found for tenant")
        if cat.archived_at is not None:
            raise CrmError("invalid_category", "Category is archived")
        return cat

    def _category_name(self, tenant_id: UUID, category_id: UUID | None) -> str | None:
        if category_id is None:
            return None
        return self._session.scalar(
            select(ServiceCategory.name).where(
                ServiceCategory.id == category_id,
                ServiceCategory.tenant_id == tenant_id,
            )
        )

    @staticmethod
    def _parse_duration(value: int | None) -> int | None:
        if value is None:
            return None
        duration = int(value)
        if duration <= 0:
            raise CrmError("invalid_duration", "duration_minutes must be positive")
        if duration > 10080:
            raise CrmError("invalid_duration", "duration_minutes exceeds one week")
        return duration
