"""Base adapter helpers shared by all providers."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from callbot_platform.integrations.constants import HealthStatus
from callbot_platform.integrations.errors import UnsupportedOperationError
from callbot_platform.integrations.protocols import (
    HealthResult,
    ProviderDescriptor,
    SyncPage,
)


class BaseProviderAdapter:
    descriptor: ProviderDescriptor

    def health_check(self, *, credentials: dict[str, Any] | None) -> HealthResult:
        if not credentials or not credentials.get("has_access_token"):
            return HealthResult(
                status=HealthStatus.AUTH_REQUIRED,
                message="Not connected or credentials missing",
            )
        return HealthResult(status=HealthStatus.HEALTHY, message="Credentials present")

    def sync_page(
        self,
        *,
        tenant_id: UUID,
        credentials: dict[str, Any] | None,
        cursor: str | None,
        direction: str,
    ) -> SyncPage:
        """Default: no remote pages until provider credentials + live API are verified."""
        _ = (tenant_id, credentials, cursor, direction)
        return SyncPage(items=[], next_cursor=None, done=True)

    def require_capability(self, capability: str) -> None:
        caps = {c.value for c in self.descriptor.capabilities}
        if capability not in caps:
            raise UnsupportedOperationError(
                f"{self.descriptor.name} does not support {capability}"
            )
