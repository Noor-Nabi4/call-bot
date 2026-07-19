"""Business information included in the system prompt."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class BusinessFacts:
    """Version-controlled / env-provided facts the agent is allowed to speak."""

    hours: str | None = None
    service_area: str | None = None
    phone: str | None = None
    address: str | None = None
    services: str | None = None
    extra: str | None = None


def business_information(
    business_name: str,
    facts: BusinessFacts | None = None,
) -> str:
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
        "have that information and offer to take a message or suggest another "
        "way they can get help. Never invent hours, prices, policies, or "
        "addresses. For appointment availability, use get_available_slots — "
        "do not invent open times."
    )
