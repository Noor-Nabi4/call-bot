"""Response provenance helpers — authoritative vs unknown operational facts.

Does not invent a parallel verification pipeline. Callers use tool results as
the only source of truth for AuthoritativeData categories.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from callbot_platform.ai_guardrails.authoritative import AuthoritativeData


class FactProvenance(StrEnum):
    AUTHORITATIVE_TOOL = "AUTHORITATIVE_TOOL"
    GENERAL_KNOWLEDGE = "GENERAL_KNOWLEDGE"
    UNKNOWN = "UNKNOWN"


UNAVAILABLE_CUSTOMER_MESSAGE = "I don't have that information available right now."


def classify_operational_claim(
    *,
    category: AuthoritativeData | str,
    tool_ok: bool,
    tool_payload: dict[str, Any] | None,
) -> FactProvenance:
    """Classify whether an operational claim may be stated as fact.

    Fail closed: missing/failed tool → UNKNOWN (must not invent).
    """
    _ = AuthoritativeData(category)
    if not tool_ok or tool_payload is None:
        return FactProvenance.UNKNOWN
    return FactProvenance.AUTHORITATIVE_TOOL


def may_state_as_fact(provenance: FactProvenance) -> bool:
    return provenance == FactProvenance.AUTHORITATIVE_TOOL


def unavailable_message() -> str:
    return UNAVAILABLE_CUSTOMER_MESSAGE
