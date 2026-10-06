"""Central tenant → database resolution (shared today, dedicated later)."""

from __future__ import annotations

import logging
from dataclasses import dataclass
from enum import StrEnum
from threading import Lock
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings

logger = logging.getLogger(__name__)


class DatabaseStrategy(StrEnum):
    SHARED = "shared"
    DEDICATED = "dedicated"


@dataclass(frozen=True, slots=True)
class ResolvedDatabase:
    """Resolved bind for a tenant. DSNs for dedicated DBs come from secrets."""

    tenant_id: UUID
    strategy: DatabaseStrategy
    database_url: str
    dsn_key: str | None = None


class TenantDatabaseResolver:
    """
    Resolve which database URL a tenant should use.

    Shared strategy uses the process default DATABASE_URL.
    Dedicated strategy looks up an opaque dsn_key in a secrets map
    (env/settings for now; secrets manager later). Raw DSNs are never
    stored on the tenants row.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        dedicated_dsn_map: dict[str, str] | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._dedicated_dsn_map = dict(dedicated_dsn_map or {})
        self._lock = Lock()

    def register_dedicated_dsn(self, dsn_key: str, database_url: str) -> None:
        key = dsn_key.strip()
        if not key or not database_url.strip():
            raise ValueError("dsn_key and database_url are required")
        with self._lock:
            self._dedicated_dsn_map[key] = database_url.strip()

    def resolve(
        self,
        tenant_id: UUID,
        *,
        session: Session | None = None,
        strategy: DatabaseStrategy | str | None = None,
        dsn_key: str | None = None,
    ) -> ResolvedDatabase:
        """
        Resolve DB bind for tenant_id.

        If session is provided, read strategy columns from tenants when present.
        Callers may also pass strategy/dsn_key explicitly (tests / migration tools).
        """
        resolved_strategy = DatabaseStrategy.SHARED
        resolved_key: str | None = None

        if strategy is not None:
            resolved_strategy = DatabaseStrategy(strategy)
            resolved_key = dsn_key
        elif session is not None:
            row = self._load_tenant_routing(session, tenant_id)
            if row is not None:
                resolved_strategy = DatabaseStrategy(
                    row.get("db_strategy") or DatabaseStrategy.SHARED
                )
                resolved_key = row.get("db_dsn_key")

        if resolved_strategy == DatabaseStrategy.SHARED:
            return ResolvedDatabase(
                tenant_id=tenant_id,
                strategy=DatabaseStrategy.SHARED,
                database_url=self._settings.database_url,
                dsn_key=None,
            )

        if not resolved_key:
            logger.error(
                "dedicated_strategy_missing_dsn_key",
                extra={"tenant_id": str(tenant_id)},
            )
            raise ValueError(
                f"Tenant {tenant_id} is dedicated but db_dsn_key is not set"
            )

        url = self._dedicated_dsn_map.get(resolved_key)
        if not url:
            # Dedicated DSNs are injected via register_dedicated_dsn / constructor map.
            logger.error(
                "dedicated_dsn_not_configured",
                extra={"tenant_id": str(tenant_id), "dsn_key": resolved_key},
            )
            raise ValueError(f"No database URL configured for dsn_key={resolved_key!r}")

        return ResolvedDatabase(
            tenant_id=tenant_id,
            strategy=DatabaseStrategy.DEDICATED,
            database_url=url,
            dsn_key=resolved_key,
        )

    def _load_tenant_routing(
        self, session: Session, tenant_id: UUID
    ) -> dict[str, Any] | None:
        from callbot_platform.db.models import Tenant

        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            return None
        return {
            "db_strategy": getattr(tenant, "db_strategy", DatabaseStrategy.SHARED),
            "db_dsn_key": getattr(tenant, "db_dsn_key", None),
        }


_resolver: TenantDatabaseResolver | None = None
_resolver_lock = Lock()


def get_tenant_database_resolver() -> TenantDatabaseResolver:
    global _resolver
    with _resolver_lock:
        if _resolver is None:
            _resolver = TenantDatabaseResolver()
        return _resolver
