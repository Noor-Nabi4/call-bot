"""Provider protocols — core depends only on these interfaces."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Protocol
from uuid import UUID

from callbot_platform.integrations.constants import (
    Capability,
    HealthStatus,
    IntegrationCategory,
)


@dataclass(frozen=True)
class ProviderDescriptor:
    key: str
    name: str
    category: IntegrationCategory
    description: str
    capabilities: frozenset[Capability]
    oauth: bool = True
    default_sync_direction: str = "IMPORT"


@dataclass
class ExternalCustomer:
    external_id: str
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalLead:
    external_id: str
    title: str | None = None
    email: str | None = None
    phone: str | None = None
    status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalAppointment:
    external_id: str
    title: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    timezone: str | None = None
    status: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalProduct:
    external_id: str
    name: str | None = None
    sku: str | None = None
    price: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalOrder:
    external_id: str
    order_number: str | None = None
    status: str | None = None
    total: float | None = None
    currency: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalInvoice:
    external_id: str
    invoice_number: str | None = None
    status: str | None = None
    total: float | None = None
    balance_due: float | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class ExternalPayment:
    external_id: str
    amount: float | None = None
    status: str | None = None
    currency: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)


@dataclass
class SyncPage:
    items: list[Any]
    next_cursor: str | None = None
    done: bool = False


@dataclass
class HealthResult:
    status: HealthStatus
    message: str | None = None


class IntegrationProvider(Protocol):
    descriptor: ProviderDescriptor

    def health_check(self, *, credentials: dict[str, Any] | None) -> HealthResult: ...

    def sync_page(
        self,
        *,
        tenant_id: UUID,
        credentials: dict[str, Any] | None,
        cursor: str | None,
        direction: str,
    ) -> SyncPage: ...
