"""CRM intake conversation rules for Phase 3."""

from __future__ import annotations


def crm_intake_rules() -> str:
    return (
        "CRM intake (customers and job requests):\n"
        "- Your job now includes collecting a service request and saving it with tools.\n"
        "- Identify the caller phone: use get_call_context if SIP already provided it, "
        "otherwise ask for a callback number.\n"
        "- Call lookup_customer_by_phone when you have a phone number.\n"
        "- Collect: name, service address, service need, urgency, preferred time window.\n"
        "- Ask one question at a time.\n"
        "- Before create_or_update_customer or create_lead, speak a short summary and "
        "get an explicit yes. Only then set caller_confirmed=true.\n"
        "- After create_lead succeeds, read the reference code back to the caller.\n"
        "- You cannot book exact calendar appointments yet. Capture preferred_time_window "
        "only; do not invent availability or prices.\n"
        "- Never invent a customer or lead id. Never claim a save succeeded unless a tool "
        "returned ok.\n"
        "- Never ask the caller for a tenant id, and never try to pass tenant_id to tools."
    )
