"""Platform permission catalog and system role templates.

Permissions are platform-defined. Organizations assign them to roles;
organizations cannot invent new permission keys.
"""

from __future__ import annotations

from typing import Final

SCOPE_ALL = "ALL_ORGANIZATION"
SCOPE_OWN = "OWN"
SCOPE_ASSIGNED = "ASSIGNED"
SCOPE_TEAM = "TEAM"

VALID_SCOPES: Final[frozenset[str]] = frozenset(
    {SCOPE_ALL, SCOPE_OWN, SCOPE_ASSIGNED, SCOPE_TEAM}
)

SOURCE_SYSTEM_DEFAULT = "SYSTEM_DEFAULT"
SOURCE_ORG_CUSTOM = "ORG_CUSTOM"
VALID_PERMISSION_SOURCES: Final[frozenset[str]] = frozenset(
    {SOURCE_SYSTEM_DEFAULT, SOURCE_ORG_CUSTOM}
)

# (resource, action, description)
PERMISSION_CATALOG: Final[tuple[tuple[str, str, str], ...]] = (
    ("customers", "read", "View customers"),
    ("customers", "create", "Create customers"),
    ("customers", "update", "Update customers"),
    ("leads", "read", "View leads"),
    ("leads", "create", "Create leads"),
    ("jobs", "read", "View jobs"),
    ("jobs", "create", "Create jobs"),
    ("jobs", "update", "Update jobs"),
    ("jobs", "assign", "Assign jobs to technicians"),
    ("appointments", "read", "View appointments"),
    ("appointments", "create", "Create appointments"),
    ("appointments", "update", "Update appointments"),
    ("appointments", "cancel", "Cancel appointments"),
    ("technicians", "read", "View technicians"),
    ("technicians", "manage", "Manage technicians"),
    ("knowledge", "read", "View knowledge articles"),
    ("knowledge", "manage", "Create and edit knowledge"),
    ("calls", "read", "View calls"),
    ("calls", "update", "Update call quality / disposition"),
    ("handoff", "read", "View handoff settings and queue"),
    ("handoff", "manage", "Manage handoff settings"),
    ("ai", "read", "View AI agent configuration"),
    ("ai", "configure", "Edit AI agent configuration"),
    ("ai", "tools_crm", "AI may run CRM tools"),
    ("ai", "tools_scheduling", "AI may run scheduling tools"),
    ("ai", "tools_knowledge", "AI may run knowledge tools"),
    ("ai", "tools_handoff", "AI may request human handoff"),
    ("ai", "tools_sms", "AI may trigger SMS notifications"),
    ("organization", "read", "View organization profile"),
    ("organization", "update", "Update organization profile"),
    ("team", "read", "View organization members"),
    ("team", "manage", "Invite and update members"),
    ("roles", "read", "View roles and permissions"),
    ("roles", "create", "Create custom roles"),
    ("roles", "update", "Update roles and permissions"),
    ("roles", "delete", "Deactivate or delete custom roles"),
    ("roles", "assign", "Assign roles to members"),
    ("analytics", "read", "View analytics and metrics"),
    ("automations", "read", "View automation rules"),
    ("automations", "manage", "Manage automation rules"),
    ("billing", "read", "View billing and usage"),
    ("billing", "manage", "Manage billing portal / checkout"),
    ("phones", "manage", "Manage phone numbers"),
    ("agents", "manage", "Manage agent profiles"),
    ("api_keys", "manage", "Manage API keys"),
    ("branding", "manage", "Manage tenant branding"),
)

SYSTEM_ROLE_OWNER = "Owner"
SYSTEM_ROLE_ADMIN = "Admin"
SYSTEM_ROLE_MANAGER = "Manager"
SYSTEM_ROLE_DISPATCHER = "Dispatcher"
SYSTEM_ROLE_TECHNICIAN = "Technician"
SYSTEM_ROLE_CSR = "CSR"
SYSTEM_ROLE_ACCOUNTANT = "Accountant"
SYSTEM_ROLE_AI_AGENT = "AI Agent"

SYSTEM_ROLE_NAMES: Final[tuple[str, ...]] = (
    SYSTEM_ROLE_OWNER,
    SYSTEM_ROLE_ADMIN,
    SYSTEM_ROLE_MANAGER,
    SYSTEM_ROLE_DISPATCHER,
    SYSTEM_ROLE_TECHNICIAN,
    SYSTEM_ROLE_CSR,
    SYSTEM_ROLE_ACCOUNTANT,
    SYSTEM_ROLE_AI_AGENT,
)

# Legacy string role on tenant_users → system role name
LEGACY_ROLE_MAP: Final[dict[str, str]] = {
    "admin": SYSTEM_ROLE_ADMIN,
    "dispatcher": SYSTEM_ROLE_DISPATCHER,
    "technician": SYSTEM_ROLE_TECHNICIAN,
}

# Compatibility: system role → legacy JWT / UI string (primary display role)
SYSTEM_TO_LEGACY: Final[dict[str, str]] = {
    SYSTEM_ROLE_OWNER: "admin",
    SYSTEM_ROLE_ADMIN: "admin",
    SYSTEM_ROLE_MANAGER: "dispatcher",
    SYSTEM_ROLE_DISPATCHER: "dispatcher",
    SYSTEM_ROLE_TECHNICIAN: "technician",
    SYSTEM_ROLE_CSR: "dispatcher",
    SYSTEM_ROLE_ACCOUNTANT: "admin",
    SYSTEM_ROLE_AI_AGENT: "admin",
}

PROTECTED_SYSTEM_ROLES: Final[frozenset[str]] = frozenset(
    {SYSTEM_ROLE_OWNER, SYSTEM_ROLE_ADMIN, SYSTEM_ROLE_AI_AGENT}
)

# Permissions that non-Owner actors cannot grant onto roles (Owner may grant).
# Role assignment of Owner itself is gated separately in RoleRepository.
OWNER_ONLY_PERMISSIONS: Final[frozenset[str]] = frozenset(
    {
        "api_keys.manage",
    }
)

# Tool-group → permission key for AI authorization
AI_TOOL_PERMISSIONS: Final[dict[str, str]] = {
    "crm": "ai.tools_crm",
    "scheduling": "ai.tools_scheduling",
    "knowledge": "ai.tools_knowledge",
    "handoff": "ai.tools_handoff",
    "sms": "ai.tools_sms",
}


def permission_key(resource: str, action: str) -> str:
    return f"{resource}.{action}"


def all_permission_keys() -> frozenset[str]:
    return frozenset(permission_key(r, a) for r, a, _ in PERMISSION_CATALOG)


def default_role_permissions(role_name: str) -> list[tuple[str, str]]:
    """Return (permission_key, scope) pairs for a system role template."""
    all_keys = sorted(all_permission_keys())
    if role_name == SYSTEM_ROLE_OWNER:
        return [(k, SCOPE_ALL) for k in all_keys]
    if role_name == SYSTEM_ROLE_ADMIN:
        return [(k, SCOPE_ALL) for k in all_keys if k not in OWNER_ONLY_PERMISSIONS]
    if role_name == SYSTEM_ROLE_MANAGER:
        keys = [
            "customers.read",
            "customers.create",
            "customers.update",
            "leads.read",
            "leads.create",
            "jobs.read",
            "jobs.create",
            "jobs.update",
            "jobs.assign",
            "appointments.read",
            "appointments.create",
            "appointments.update",
            "appointments.cancel",
            "technicians.read",
            "technicians.manage",
            "knowledge.read",
            "calls.read",
            "calls.update",
            "handoff.read",
            "handoff.manage",
            "analytics.read",
            "team.read",
            "ai.read",
        ]
        return [(k, SCOPE_ALL) for k in keys]
    if role_name == SYSTEM_ROLE_DISPATCHER:
        keys = [
            "customers.read",
            "customers.create",
            "customers.update",
            "leads.read",
            "leads.create",
            "jobs.read",
            "jobs.create",
            "jobs.update",
            "jobs.assign",
            "appointments.read",
            "appointments.create",
            "appointments.update",
            "appointments.cancel",
            "technicians.read",
            "technicians.manage",
            "knowledge.read",
            "knowledge.manage",
            "calls.read",
            "calls.update",
            "handoff.read",
            "handoff.manage",
            "analytics.read",
        ]
        return [(k, SCOPE_ALL) for k in keys]
    if role_name == SYSTEM_ROLE_TECHNICIAN:
        return [
            ("jobs.read", SCOPE_ASSIGNED),
            ("jobs.update", SCOPE_ASSIGNED),
            ("customers.read", SCOPE_ASSIGNED),
            ("appointments.read", SCOPE_ASSIGNED),
            ("calls.read", SCOPE_ASSIGNED),
        ]
    if role_name == SYSTEM_ROLE_CSR:
        keys = [
            "customers.read",
            "customers.create",
            "customers.update",
            "leads.read",
            "leads.create",
            "appointments.read",
            "appointments.create",
            "appointments.update",
            "appointments.cancel",
            "knowledge.read",
            "calls.read",
            "handoff.read",
        ]
        return [(k, SCOPE_ALL) for k in keys]
    if role_name == SYSTEM_ROLE_ACCOUNTANT:
        keys = [
            "customers.read",
            "billing.read",
            "analytics.read",
            "calls.read",
        ]
        return [(k, SCOPE_ALL) for k in keys]
    if role_name == SYSTEM_ROLE_AI_AGENT:
        return [
            ("customers.read", SCOPE_ALL),
            ("customers.create", SCOPE_ALL),
            ("customers.update", SCOPE_ALL),
            ("leads.create", SCOPE_ALL),
            ("appointments.read", SCOPE_ALL),
            ("appointments.create", SCOPE_ALL),
            ("appointments.update", SCOPE_ALL),
            ("appointments.cancel", SCOPE_ALL),
            ("jobs.create", SCOPE_ALL),
            ("knowledge.read", SCOPE_ALL),
            ("ai.tools_crm", SCOPE_ALL),
            ("ai.tools_scheduling", SCOPE_ALL),
            ("ai.tools_knowledge", SCOPE_ALL),
            ("ai.tools_handoff", SCOPE_ALL),
            ("ai.tools_sms", SCOPE_ALL),
        ]
    return []
