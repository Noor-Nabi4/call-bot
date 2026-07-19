"""Assemble versioned system instructions for the voice agent."""

from __future__ import annotations

from prompts.business import BusinessFacts, business_information
from prompts.crm import crm_intake_rules
from prompts.handoff import handoff_rules
from prompts.knowledge import knowledge_rules
from prompts.safety import safety_rules
from prompts.scheduling import scheduling_rules
from prompts.system import (
    call_ending_rules,
    conversation_rules,
    core_identity,
    unsupported_request_rules,
    voice_style,
)


def build_system_instructions(
    *,
    business_name: str,
    max_spoken_sentences: int,
    language: str,
    business_facts: BusinessFacts | None = None,
) -> str:
    language_rule = (
        f"Language: Prefer speaking in language code '{language}'. "
        "If the caller clearly uses another language, match the caller."
    )
    return "\n\n".join(
        [
            core_identity(business_name),
            business_information(business_name, business_facts),
            voice_style(max_spoken_sentences),
            language_rule,
            conversation_rules(),
            crm_intake_rules(),
            scheduling_rules(),
            knowledge_rules(),
            handoff_rules(),
            unsupported_request_rules(),
            safety_rules(),
            call_ending_rules(),
        ]
    )
