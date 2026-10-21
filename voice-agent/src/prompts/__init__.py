"""Assemble versioned system instructions for the voice agent."""

from __future__ import annotations

from prompts.business import (
    BusinessFacts,
    bootstrap_instructions,
    business_information,
    call_context_section,
    tenant_business_rules_section,
    tenant_conversation_preferences,
    tenant_identity_section,
)
from prompts.call_flow import render_call_flow_section
from prompts.safety import platform_safety_rules
from prompts.system import (
    call_ending_rules,
    core_voice_behavior,
    unsupported_request_rules,
)
from prompts.tool_rules import tool_usage_rules
from tenant.agent_profile import AgentProfile, CallFacts

PROMPT_COMPOSITION_VERSION = "prompt-compose-v5"


def build_system_instructions_from_profile(
    profile: AgentProfile,
    *,
    max_spoken_sentences: int | None = None,
    call_facts: CallFacts | None = None,
) -> str:
    """Compose tenant-aware instructions in the required priority order.

    Order:
      1. Platform safety
      2. Core voice behavior
      3. Tenant identity
      4. Tenant business rules
      5. Tenant conversation preferences (custom instructions delimited)
      6. Ordered call flow (when configured)
      7. Tool usage rules (enabled tools only; isolation rules always)
      8. Current call context
    """
    sentences = max_spoken_sentences or profile.max_spoken_sentences()
    sections = [
        f"[prompt-composition {PROMPT_COMPOSITION_VERSION}]",
        platform_safety_rules(),
        core_voice_behavior(max_spoken_sentences=sentences),
        tenant_identity_section(profile),
        tenant_business_rules_section(profile),
        tenant_conversation_preferences(profile),
    ]
    flow_section = render_call_flow_section(profile.call_flow)
    if flow_section:
        sections.append(flow_section)
    sections.extend(
        [
            tool_usage_rules(profile.enabled_tools),
            unsupported_request_rules(),
            call_ending_rules(),
            call_context_section(call_facts),
        ]
    )
    return "\n\n".join(sections)


def build_system_instructions(
    *,
    business_name: str,
    max_spoken_sentences: int,
    language: str,
    business_facts: BusinessFacts | None = None,
    profile: AgentProfile | None = None,
    call_facts: CallFacts | None = None,
) -> str:
    """Build instructions from a profile when available; else legacy local helper."""
    if profile is not None:
        return build_system_instructions_from_profile(
            profile,
            max_spoken_sentences=max_spoken_sentences,
            call_facts=call_facts,
        )

    # Legacy path for unit/eval tests that still pass BusinessFacts directly.
    # Production call startup must use build_system_instructions_from_profile.
    language_rule = (
        f"Language: Prefer speaking in language code '{language}'. "
        "If the caller clearly uses another language and it is appropriate, "
        "match the caller."
    )
    return "\n\n".join(
        [
            platform_safety_rules(),
            core_voice_behavior(max_spoken_sentences=max_spoken_sentences),
            f"You are a professional voice assistant for {business_name}.",
            business_information(business_name, business_facts),
            language_rule,
            tool_usage_rules(),
            unsupported_request_rules(),
            call_ending_rules(),
            call_context_section(call_facts),
        ]
    )


__all__ = [
    "PROMPT_COMPOSITION_VERSION",
    "bootstrap_instructions",
    "build_system_instructions",
    "build_system_instructions_from_profile",
]
