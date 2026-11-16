"""Phase 31 AI Guardrails — catalogs and helpers atop Phase 14/30.

Does not create a second tool executor or confirmation system.
"""

from callbot_platform.ai_guardrails.authoritative import (
    AUTHORITATIVE_INJECTION_KEYS,
    AuthoritativeData,
    list_authoritative_categories,
    tools_for_category,
)
from callbot_platform.ai_guardrails.confirmation_ops import (
    ConfirmationOperation,
    assert_minimum_confirmation_coverage,
    confirmation_required_for_tool,
    list_confirmation_required_tools,
    operation_for_tool,
)
from callbot_platform.ai_guardrails.provenance import (
    FactProvenance,
    classify_operational_claim,
    may_state_as_fact,
    unavailable_message,
)

__all__ = [
    "AUTHORITATIVE_INJECTION_KEYS",
    "AuthoritativeData",
    "ConfirmationOperation",
    "FactProvenance",
    "assert_minimum_confirmation_coverage",
    "classify_operational_claim",
    "confirmation_required_for_tool",
    "list_authoritative_categories",
    "list_confirmation_required_tools",
    "may_state_as_fact",
    "operation_for_tool",
    "tools_for_category",
    "unavailable_message",
]
