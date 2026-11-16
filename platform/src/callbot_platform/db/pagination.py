"""Shared pagination helpers for tenant-scoped list APIs."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class PageParams:
    """Bounded limit for list endpoints. Prefer keyset cursors for hot tables."""

    limit: int
    offset: int = 0

    @classmethod
    def parse(
        cls,
        *,
        limit: int | None = None,
        offset: int | None = None,
        default_limit: int = 50,
        max_limit: int = 200,
    ) -> PageParams:
        resolved_limit = default_limit if limit is None else int(limit)
        if resolved_limit < 1:
            resolved_limit = 1
        if resolved_limit > max_limit:
            resolved_limit = max_limit
        resolved_offset = 0 if offset is None else max(0, int(offset))
        return cls(limit=resolved_limit, offset=resolved_offset)
