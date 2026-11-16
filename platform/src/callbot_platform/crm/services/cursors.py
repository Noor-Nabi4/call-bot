"""Keyset cursors for services & pricebook lists."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from callbot_platform.db.pagination import PageParams


@dataclass(frozen=True, slots=True)
class ServiceCursor:
    updated_at: datetime
    id: UUID

    def encode(self) -> str:
        raw = json.dumps(
            {"u": self.updated_at.isoformat(), "i": str(self.id)},
            separators=(",", ":"),
        )
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")

    @classmethod
    def decode(cls, token: str | None) -> ServiceCursor | None:
        if not token or not token.strip():
            return None
        try:
            raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
            data = json.loads(raw)
            return cls(
                updated_at=datetime.fromisoformat(str(data["u"])),
                id=UUID(str(data["i"])),
            )
        except (KeyError, ValueError, json.JSONDecodeError, TypeError) as exc:
            raise ValueError("invalid_cursor") from exc


def parse_service_page(
    *,
    limit: int | None,
    cursor: str | None,
    max_limit: int = 200,
    default_limit: int = 50,
) -> tuple[PageParams, ServiceCursor | None]:
    page = PageParams.parse(
        limit=limit, default_limit=default_limit, max_limit=max_limit
    )
    decoded = ServiceCursor.decode(cursor) if cursor else None
    return page, decoded
