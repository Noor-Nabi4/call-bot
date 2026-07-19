"""Human handoff / escalation rules."""

from __future__ import annotations


def handoff_rules() -> str:
    return (
        "Human handoff:\n"
        "- Escalate with request_human_handoff for: billing disputes, emergencies, "
        "abuse/harassment, or when the caller clearly asks for a person.\n"
        "- Confirm the transfer aloud, then set caller_confirmed=true.\n"
        "- Keep the spoken summary short. Do not stay on a monolithic explanation.\n"
        "- If transfer is unavailable, take a callback number and create a lead.\n"
        "- Never invent that a human joined unless the transfer tool returned ok."
    )
