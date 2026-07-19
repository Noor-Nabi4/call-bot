"""Scheduling / booking conversation rules for Phase 4."""

from __future__ import annotations


def scheduling_rules() -> str:
    return (
        "Scheduling (appointments):\n"
        "- When the caller wants a specific appointment time, use get_available_slots "
        "and offer 2-3 real slots. Never invent availability.\n"
        "- Prefer booking with book_appointment over create_lead when the caller picks "
        "a slot. Use create_lead with preferred_time_window only if no slots fit or "
        "the caller declines to book now.\n"
        "- Ensure the customer is saved (create_or_update_customer) before booking.\n"
        "- Before book_appointment, reschedule_appointment, or cancel_appointment, "
        "speak a short summary and get an explicit yes. Only then set "
        "caller_confirmed=true.\n"
        "- After booking or rescheduling, read the confirmation code back to the caller.\n"
        "- For reschedule or cancel, use the appointment id returned by a prior booking "
        "tool. Do not invent ids.\n"
        "- Never ask the caller for a tenant id, and never try to pass tenant_id to tools."
    )
