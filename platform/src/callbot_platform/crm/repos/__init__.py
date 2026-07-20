"""CRM repositories package — re-exports for import compatibility."""

from __future__ import annotations

from callbot_platform.crm.errors import CrmError
from callbot_platform.crm.repos.agent_profile_repo import AgentProfileRepository
from callbot_platform.crm.repos.agent_settings_repo import AgentSettingsRepository
from callbot_platform.crm.repos.call_repo import CallRepository
from callbot_platform.crm.repos.customer_repo import CustomerRepository
from callbot_platform.crm.repos.lead_repo import LeadRepository

__all__ = [
    "AgentProfileRepository",
    "AgentSettingsRepository",
    "CallRepository",
    "CrmError",
    "CustomerRepository",
    "LeadRepository",
]
