"""Dedicated tenant database engine cache (bounded, idle dispose)."""

from __future__ import annotations

import logging
import time
from threading import Lock
from uuid import UUID

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.config import Settings, get_settings
from callbot_platform.tenancy.strategy import (
    DatabaseStrategy,
    ResolvedDatabase,
    TenantDatabaseResolver,
    get_tenant_database_resolver,
)

logger = logging.getLogger(__name__)


class DedicatedEngineCache:
    """
    Lazy engines for dedicated tenants.

    Does not keep a permanent large pool for every inactive tenant:
    engines idle longer than dedicated_db_idle_seconds are disposed.
    """

    def __init__(
        self,
        settings: Settings | None = None,
        *,
        resolver: TenantDatabaseResolver | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._resolver = resolver or get_tenant_database_resolver()
        self._lock = Lock()
        self._engines: dict[str, tuple[Engine, sessionmaker[Session], float]] = {}

    def session_factory_for(
        self,
        tenant_id: UUID,
        *,
        session: Session | None = None,
    ) -> sessionmaker[Session]:
        resolved = self._resolver.resolve(tenant_id, session=session)
        if resolved.strategy == DatabaseStrategy.SHARED:
            from callbot_platform.db import get_session_factory

            return get_session_factory()
        return self._factory_for_resolved(resolved)

    def _factory_for_resolved(
        self, resolved: ResolvedDatabase
    ) -> sessionmaker[Session]:
        if not resolved.dsn_key:
            raise ValueError("dedicated resolution missing dsn_key")
        key = resolved.dsn_key
        now = time.monotonic()
        with self._lock:
            self._dispose_idle_locked(now)
            entry = self._engines.get(key)
            if entry is not None:
                engine, factory, _ = entry
                self._engines[key] = (engine, factory, now)
                return factory
            # Small bounded pool per dedicated DB (not the full API pool size).
            engine = create_engine(
                resolved.database_url,
                future=True,
                pool_size=min(2, self._settings.db_pool_size),
                max_overflow=min(2, self._settings.db_max_overflow),
                pool_timeout=self._settings.db_pool_timeout,
                pool_recycle=self._settings.db_pool_recycle,
                pool_pre_ping=self._settings.db_pool_pre_ping,
            )
            factory = sessionmaker(
                bind=engine, autoflush=False, autocommit=False, future=True
            )
            self._engines[key] = (engine, factory, now)
            logger.info(
                "dedicated_engine_created",
                extra={"dsn_key": key, "tenant_id": str(resolved.tenant_id)},
            )
            return factory

    def _dispose_idle_locked(self, now: float) -> None:
        idle = float(self._settings.dedicated_db_idle_seconds)
        stale = [k for k, (_, _, ts) in self._engines.items() if now - ts > idle]
        for key in stale:
            engine, _, _ = self._engines.pop(key)
            engine.dispose()
            logger.info("dedicated_engine_disposed", extra={"dsn_key": key})

    def active_engine_count(self) -> int:
        with self._lock:
            return len(self._engines)

    def dispose_all(self) -> None:
        with self._lock:
            for _key, (engine, _, _) in list(self._engines.items()):
                engine.dispose()
            self._engines.clear()
