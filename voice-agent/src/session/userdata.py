"""Session userdata bound after tenant resolve (never from the LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class SessionUserData:
    tenant_id: str
    call_id: str
    room_name: str
    business_name: str
    platform_call_id: str | None = None
    customer_id: str | None = None
    caller_number: str | None = None
    called_number: str | None = None
    is_sip: bool = False
    extra: dict[str, Any] = field(default_factory=dict)
