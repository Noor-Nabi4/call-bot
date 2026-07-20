"""Public marketing voice-demo mode — no tenant, no CRM/tools."""

from __future__ import annotations

import json
import os
from typing import Any

from tenant.agent_profile import AgentProfile
from tenant.resolve import TenantResolution, verify_signed_metadata

MARKETING_TENANT_ID = "marketing-demo"
MARKETING_SOURCE = "marketing"


def marketing_demo_profile() -> AgentProfile:
    """Fixed VoxPilot demo persona for the public landing-page voice demo."""
    return AgentProfile(
        tenant_id=MARKETING_TENANT_ID,
        business_name="VoxPilot",
        agent_profile_id="marketing-demo",
        name="VoxPilot Demo",
        agent_type="receptionist",
        assistant_name="VoxPilot",
        business_description=(
            "VoxPilot is an AI Voice Platform for service businesses and call centers. "
            "This is a public product demo — not a real business receptionist."
        ),
        greeting=(
            "Hi — I'm VoxPilot, a live demo of our AI voice platform. "
            "Ask me how VoxPilot answers calls, books appointments, or hands off to a human."
        ),
        tone="friendly, clear, and concise",
        default_language="en",
        supported_languages=("en",),
        response_style="concise",
        service_areas=(),
        business_hours_summary=None,
        booking_rules=(
            "This is a demo only. Do not book real appointments or collect personal data "
            "beyond what the visitor volunteers for the conversation."
        ),
        pricing_disclosure_policy=(
            "You may describe VoxPilot plans at a high level. Do not invent exact prices; "
            "point visitors to the pricing section on the website for current rates."
        ),
        handoff_rules="There is no live human handoff in the marketing demo.",
        restricted_topics=(
            "do not collect payment cards",
            "do not claim to represent a specific customer business",
            "do not access or invent CRM records",
        ),
        custom_instructions=(
            "You are running a public marketing demo. Keep answers short. "
            "Focus on VoxPilot capabilities: 24/7 answering, booking, knowledge lookup, "
            "and human handoff for paying tenants. "
            "If asked to perform tenant-specific CRM actions, explain that those run "
            "after signup inside the Ops console playground."
        ),
        enabled_tools=(),
        call_flow=None,
        profile_version=1,
        updated_at=None,
        voice=None,
    )


def marketing_demo_resolution() -> TenantResolution:
    return TenantResolution(
        tenant_id=MARKETING_TENANT_ID,
        phone_number_id=None,
        e164=None,
        source=MARKETING_SOURCE,
        agent_profile_id="marketing-demo",
    )


def _parse_metadata_body(raw: str | None, secret: str) -> dict[str, Any] | None:
    if not raw or not raw.strip():
        return None
    if secret:
        return verify_signed_metadata(raw, secret)
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return None
    return data if isinstance(data, dict) else None


def is_marketing_demo_metadata(
    job_metadata: str | None,
    *,
    secret: str | None = None,
    is_sip: bool = False,
) -> bool:
    """True when job metadata requests the public marketing demo (never for SIP)."""
    if is_sip:
        return False
    hmac_secret = (
        secret if secret is not None else os.getenv("METADATA_HMAC_SECRET", "").strip()
    )
    body = _parse_metadata_body(job_metadata, hmac_secret)
    if not body:
        return False
    source = body.get("source")
    return isinstance(source, str) and source.strip().lower() == MARKETING_SOURCE
