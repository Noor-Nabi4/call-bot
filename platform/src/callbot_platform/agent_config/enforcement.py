"""Server-side capability enforcement for the AI tool executor.

Configuration enables capabilities. Configuration does not bypass authorization.

Runtime rule:
- No agent profile → skip capability gate (legacy RBAC-only tenants).
- Draft / archived profile → fail closed for mapped tools (cannot authorize).
- Active profile → enforce explicit capability map.
"""

from __future__ import annotations

import logging
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.agent_config.capabilities import (
    TOOL_TO_CAPABILITY,
    capabilities_from_enabled_tools,
    normalize_capabilities,
)
from callbot_platform.agent_config.errors import AgentConfigError
from callbot_platform.crm.repos.agent_profile_repo import AgentProfileRepository

logger = logging.getLogger(__name__)

FACTS_CAPABILITIES_KEY = "capabilities"


def load_profile_capabilities(
    session: Session, tenant_id: UUID, *, profile_id: UUID | None = None
) -> dict[str, bool] | None:
    """Return capability map for an *active* profile, or None when absent.

    Raises AgentConfigError when a profile exists but is not active — draft
    configuration must not authorize live tool execution.
    """
    repo = AgentProfileRepository(session)
    if profile_id is not None:
        profile = repo.get(tenant_id, profile_id)
    else:
        profile = repo.get_default(tenant_id)
    if profile is None:
        return None
    status = str(profile.get("status") or "").strip().lower()
    if status != "active":
        raise AgentConfigError(
            "AGENT_CONFIGURATION_UNAVAILABLE",
            "Agent configuration is not active",
        )
    facts = profile.get("business_prompt_facts") or {}
    raw_caps = facts.get(FACTS_CAPABILITIES_KEY) if isinstance(facts, dict) else None
    if isinstance(raw_caps, dict) and raw_caps:
        return normalize_capabilities(raw_caps)
    return capabilities_from_enabled_tools(profile.get("enabled_tools"))


def assert_tool_capability(
    session: Session,
    tenant_id: UUID,
    tool_name: str,
    *,
    profile_id: UUID | None = None,
) -> None:
    """Raise AgentConfigError when the tool's capability is disabled."""
    cap_key = TOOL_TO_CAPABILITY.get(tool_name)
    if cap_key is None:
        return
    try:
        caps = load_profile_capabilities(session, tenant_id, profile_id=profile_id)
    except AgentConfigError:
        raise
    except Exception as exc:
        logger.warning(
            "agent_capability_load_failed tenant_id=%s error_type=%s",
            tenant_id,
            type(exc).__name__,
        )
        raise AgentConfigError(
            "AGENT_CONFIGURATION_UNAVAILABLE",
            "Active agent configuration is unavailable",
        ) from exc
    if caps is None:
        return
    if not caps.get(cap_key, False):
        raise AgentConfigError(
            "CAPABILITY_DISABLED",
            f"Capability {cap_key} is disabled for this agent",
        )


def resolve_runtime_capabilities(profile: dict[str, Any]) -> dict[str, bool]:
    facts = profile.get("business_prompt_facts") or {}
    raw = facts.get(FACTS_CAPABILITIES_KEY) if isinstance(facts, dict) else None
    if isinstance(raw, dict) and raw:
        return normalize_capabilities(raw)
    return capabilities_from_enabled_tools(profile.get("enabled_tools"))
