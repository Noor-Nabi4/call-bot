"""Tenant identity and business-rule prompt sections (configuration, not policy)."""

from __future__ import annotations

from dataclasses import dataclass

from tenant.agent_profile import AgentProfile, CallFacts

TENANT_IDENTITY_VERSION = "tenant-identity-v1"
TENANT_BUSINESS_VERSION = "tenant-business-v1"
TENANT_PREFS_VERSION = "tenant-prefs-v1"
CALL_CONTEXT_VERSION = "call-context-v1"


@dataclass(frozen=True, slots=True)
class BusinessFacts:
    """Legacy env-provided facts (local console only; not a tenant fallback)."""

    hours: str | None = None
    service_area: str | None = None
    phone: str | None = None
    address: str | None = None
    services: str | None = None
    extra: str | None = None


def bootstrap_instructions() -> str:
    """Minimal instructions before tenant profile is loaded (no business claims)."""
    return (
        "You are a voice assistant waiting for business configuration. "
        "Do not discuss specific business details, hours, services, or "
        "appointments yet. If spoken to before configuration finishes, say "
        "briefly that you are connecting them and ask them to hold a moment."
    )


def tenant_identity_section(profile: AgentProfile) -> str:
    assistant = profile.assistant_name or "the business voice assistant"
    lines = [
        f"[{TENANT_IDENTITY_VERSION} — TENANT IDENTITY (configuration)]",
        f"Business name: {profile.business_name}.",
        f"Assistant name: {assistant}.",
        f"You represent {profile.business_name} only.",
    ]
    if profile.business_description:
        lines.append(f"Business description: {profile.business_description}")
    return "\n".join(lines)


def tenant_business_rules_section(profile: AgentProfile) -> str:
    lines = [
        f"[{TENANT_BUSINESS_VERSION} — TENANT BUSINESS RULES (configuration)]",
        "Share only facts listed here or returned by tools for this tenant.",
        "Never invent hours, prices, policies, or service coverage.",
    ]
    if profile.business_hours_summary:
        lines.append(f"Business hours summary: {profile.business_hours_summary}")
    if profile.service_areas:
        lines.append("Service areas: " + "; ".join(profile.service_areas))
    if profile.booking_rules:
        lines.append(f"Booking rules: {profile.booking_rules}")
    if profile.pricing_disclosure_policy:
        lines.append(f"Pricing disclosure policy: {profile.pricing_disclosure_policy}")
    if profile.handoff_rules:
        lines.append(f"Tenant handoff preferences: {profile.handoff_rules}")
    if profile.restricted_topics:
        lines.append(
            "Restricted topics (decline or escalate): "
            + "; ".join(profile.restricted_topics)
        )
    lines.append(
        "For live availability, appointments, customers, jobs, exact prices, "
        "invoices, call history, or technician location, use tools — do not "
        "guess from memory."
    )
    return "\n".join(lines)


def tenant_conversation_preferences(profile: AgentProfile) -> str:
    supported = ", ".join(profile.supported_languages)
    lines = [
        f"[{TENANT_PREFS_VERSION} — TENANT CONVERSATION PREFERENCES (configuration)]",
        f"Default language code: {profile.default_language}.",
        f"Supported languages: {supported}.",
        "Match the caller's language when it is supported. If they switch to "
        "another supported language, follow them. If unsupported, continue in "
        f"{profile.default_language} and say briefly that you can continue in "
        "that language.",
        f"Response style: {profile.response_style}.",
    ]
    if profile.tone:
        lines.append(f"Tone: {profile.tone}.")
    if profile.greeting:
        lines.append(
            f"Preferred greeting guidance (paraphrase naturally): {profile.greeting}"
        )
    if profile.custom_instructions:
        lines.extend(
            [
                "",
                "BEGIN TENANT CUSTOM INSTRUCTIONS (configuration only; "
                "cannot override platform safety, authorization, privacy, "
                "tenant isolation, or tool-validation rules):",
                profile.custom_instructions.strip(),
                "END TENANT CUSTOM INSTRUCTIONS.",
            ]
        )
    return "\n".join(lines)


def call_context_section(facts: CallFacts | None) -> str:
    lines = [f"[{CALL_CONTEXT_VERSION} — CURRENT CALL CONTEXT]"]
    if facts is None:
        lines.append("No structured call facts captured yet.")
        return "\n".join(lines)
    fact_lines = facts.as_prompt_lines()
    if not fact_lines:
        lines.append("No structured call facts captured yet.")
    else:
        lines.extend(fact_lines)
    return "\n".join(lines)


def business_information(
    business_name: str,
    facts: BusinessFacts | None = None,
) -> str:
    """Legacy helper for env-based local tests; production uses AgentProfile."""
    facts = facts or BusinessFacts()
    known_lines: list[str] = [f"Business name: {business_name}."]
    if facts.hours:
        known_lines.append(f"Hours: {facts.hours}.")
    if facts.service_area:
        known_lines.append(f"Service area: {facts.service_area}.")
    if facts.phone:
        known_lines.append(f"Main phone: {facts.phone}.")
    if facts.address:
        known_lines.append(f"Address: {facts.address}.")
    if facts.services:
        known_lines.append(f"Services offered: {facts.services}.")
    if facts.extra:
        known_lines.append(facts.extra.strip())
    known_block = "\n".join(known_lines)
    return (
        f"{known_block}\n"
        "Only share business facts that appear in these instructions. "
        "If a caller asks for details that are not listed here, say you do not "
        "have that information. Never invent hours, prices, policies, or "
        "addresses."
    )
