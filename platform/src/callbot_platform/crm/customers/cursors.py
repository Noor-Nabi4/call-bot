"""Keyset cursors for customer list/search and timeline."""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from callbot_platform.db.pagination import PageParams


@dataclass(frozen=True, slots=True)
class CustomerCursor:
    updated_at: datetime
    id: UUID

    def encode(self) -> str:
        raw = json.dumps(
            {"u": self.updated_at.isoformat(), "i": str(self.id)},
            separators=(",", ":"),
        )
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")

    @classmethod
    def decode(cls, token: str | None) -> CustomerCursor | None:
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


@dataclass(frozen=True, slots=True)
class TimelineCursor:
    occurred_at: datetime
    source_key: str

    def encode(self) -> str:
        raw = json.dumps(
            {"t": self.occurred_at.isoformat(), "k": self.source_key},
            separators=(",", ":"),
        )
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")

    @classmethod
    def decode(cls, token: str | None) -> TimelineCursor | None:
        if not token or not token.strip():
            return None
        try:
            raw = base64.urlsafe_b64decode(token.encode("ascii")).decode("utf-8")
            data = json.loads(raw)
            return cls(
                occurred_at=datetime.fromisoformat(str(data["t"])),
                source_key=str(data["k"]),
            )
        except (KeyError, ValueError, json.JSONDecodeError, TypeError) as exc:
            raise ValueError("invalid_cursor") from exc


def parse_customer_page(
    *,
    limit: int | None,
    cursor: str | None,
    max_limit: int = 200,
    default_limit: int = 50,
) -> tuple[PageParams, CustomerCursor | None]:
    page = PageParams.parse(
        limit=limit, default_limit=default_limit, max_limit=max_limit
    )
    decoded = CustomerCursor.decode(cursor) if cursor else None
    return page, decoded


def parse_timeline_page(
    *,
    limit: int | None,
    cursor: str | None,
    max_limit: int = 100,
    default_limit: int = 50,
) -> tuple[PageParams, TimelineCursor | None]:
    page = PageParams.parse(
        limit=limit, default_limit=default_limit, max_limit=max_limit
    )
    decoded = TimelineCursor.decode(cursor) if cursor else None
    return page, decoded
