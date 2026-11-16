"""Session userdata bound after tenant resolve (never from the LLM)."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from tenant.agent_profile import AgentProfile, CallFacts


@dataclass
class SessionUserData:
    """Trusted per-call context. tenant_id is immutable after resolve."""

    tenant_id: str
    call_id: str
    room_name: str
    business_name: str
    agent_profile: AgentProfile | None = None
    agent_profile_version: int | None = None
    call_facts: CallFacts = field(default_factory=CallFacts)
    requested_language: str | None = None
    platform_call_id: str | None = None
    customer_id: str | None = None
    caller_number: str | None = None
    called_number: str | None = None
    is_sip: bool = False
    knowledge_lookup_used: bool = False
    handoff_requested: bool = False
    last_tool_name: str | None = None
    last_tool_result_status: str | None = None
    # Stable mutation operation_id + HMAC confirmation token (trusted session state).
    pending_operation_id: str | None = None
    pending_confirmation_token: str | None = None
    pending_confirmation_tool: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def record_tool_result(self, tool_name: str, *, ok: bool) -> None:
        self.last_tool_name = tool_name
        self.last_tool_result_status = "ok" if ok else "error"
        if tool_name == "search_knowledge" and ok:
            self.knowledge_lookup_used = True
        if tool_name == "request_human_handoff":
            self.handoff_requested = True
