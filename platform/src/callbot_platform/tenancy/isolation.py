"""Tenant isolation helpers for repositories, caches, and jobs."""

from __future__ import annotations

from uuid import UUID


def assert_same_tenant(
    expected_tenant_id: UUID,
    actual_tenant_id: UUID,
    *,
    resource: str = "resource",
) -> None:
    """Raise ValueError when a loaded row belongs to a different tenant."""
    if expected_tenant_id != actual_tenant_id:
        raise ValueError(
            f"Cross-tenant access denied for {resource}: "
            f"expected={expected_tenant_id} actual={actual_tenant_id}"
        )


def tenant_cache_key(tenant_id: UUID, *parts: str) -> str:
    """Build a tenant-scoped cache key. Always include tenant_id first."""
    safe_parts = [p.strip().replace(" ", "_") for p in parts if p and p.strip()]
    return ":".join(["tenant", str(tenant_id), *safe_parts])
