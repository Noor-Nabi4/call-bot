"""Multi-tenant resolution, isolation helpers, and database strategy."""

from __future__ import annotations

from callbot_platform.tenancy.context import (
    TenantContext,
    TenantSource,
    clear_tenant_context,
    get_tenant_context,
    require_tenant_context,
    set_tenant_context,
)
from callbot_platform.tenancy.isolation import assert_same_tenant, tenant_cache_key
from callbot_platform.tenancy.strategy import (
    DatabaseStrategy,
    ResolvedDatabase,
    TenantDatabaseResolver,
    get_tenant_database_resolver,
)

__all__ = [
    "DatabaseStrategy",
    "ResolvedDatabase",
    "TenantContext",
    "TenantDatabaseResolver",
    "TenantSource",
    "assert_same_tenant",
    "clear_tenant_context",
    "get_tenant_context",
    "get_tenant_database_resolver",
    "require_tenant_context",
    "set_tenant_context",
    "tenant_cache_key",
]
