# Organization-Managed RBAC

**Status:** Implemented (Task 1.3 + 1.3.1 + 1.3.2)  
**Membership model:** `tenant_users` remains canonical (Task 1.2). Do not add a parallel members table.

## Authority

```text
member_roles + role_permissions  →  authoritative authorization
tenant_users.role                →  compatibility / JWT / UI only
```

RBAC is authoritative for authorization.  
`tenant_users.role` is compatibility-only and must not be consulted as a security gate.

See also: [`RBAC_LEGACY_AUTH_AUDIT.md`](./RBAC_LEGACY_AUTH_AUDIT.md).

## Model

```text
permissions              # platform catalog (resource.action)
organization_roles       # per-tenant roles (system + custom)
role_permissions         # role_id + permission_id + scope
member_roles             # tenant_user_id + role_id
```

## System roles

Per organization: Owner, Admin, Manager, Dispatcher, Technician, CSR, Accountant, AI Agent.

- First bootstrapped admin → **Owner**
- Subsequent `admin` string roles → **Admin**
- `dispatcher` / `technician` map to the matching system roles

Owner role permissions and last-Owner removal are protected.  
Last active Owner/Admin membership is also protected via `member_roles` counts.

## Scopes (fail closed — Task 1.3.2)

`ALL_ORGANIZATION` | `OWN` | `ASSIGNED` | `TEAM`

| Scope | Missing ResourceContext | Missing scope fields |
| --- | --- | --- |
| ALL_ORGANIZATION | Allowed for org-level ops; with resource, tenant must match | N/A |
| OWN | **DENY** | **DENY** if `owner_user_id` missing |
| ASSIGNED | **DENY** | **DENY** if `assigned_technician_user_id` missing |
| TEAM | **DENY** | **DENY** if `team_user_ids` missing |

Never interpret missing assignment/ownership as allow.  
List endpoints use `AuthorizationService.list_access_mode()` (`all` / `assigned` / deny).

## Authorization flow

```text
Authentication
    → Tenant (session)
    → Membership (tenant_users, active)
    → member_roles
    → role_permissions + scope
    → ResourceContext (when scoped)
    → ALLOW / DENY
```

Dependencies:

- `require_permission(key)` / `require_entitled_permission(key)` — preferred
- `require_ops_roles` / `require_entitled_ops_roles` — **deprecated**, unused by routes

## AI tools

Call-scope still binds tenant/call. Call scope does **not** grant permissions by itself.

Internal voice tool routes call `require_ai_tool_permission(tenant_id, tool_group)` against the org **AI Agent** system role:

| Tool group  | Permission            |
| ----------- | --------------------- |
| crm         | `ai.tools_crm`        |
| scheduling  | `ai.tools_scheduling` |
| knowledge   | `ai.tools_knowledge`  |
| handoff     | `ai.tools_handoff`    |
| sms         | `ai.tools_sms`        |

AI is never treated as admin.

## APIs

```text
GET    /api/admin/organization/permissions
GET    /api/admin/organization/roles
POST   /api/admin/organization/roles
GET    /api/admin/organization/roles/{id}
PATCH  /api/admin/organization/roles/{id}
DELETE /api/admin/organization/roles/{id}
GET    /api/admin/organization/members/{id}/roles
POST   /api/admin/organization/members/{id}/roles
DELETE /api/admin/organization/members/{id}/roles/{role_id}
```

Tenant always comes from the session. Cross-tenant IDs → 404.

## Migration

Alembic `0024_organization_rbac` creates tables and backfills existing tenants.  
Tasks 1.3.1 / 1.3.2 require **no new migration** (catalog defaults sync via `ensure_system_roles_for_tenant`).

## Rollback notes

- Do not drop `tenant_users.role` until JWT/UI clients stop requiring it.
- Downgrade of `0024` drops RBAC tables only; membership rows remain intact.

## Ops UI

`/settings/roles` — list/create roles, edit permissions (Owner fixed).  
`/settings/team` — assign/remove org roles. Backend remains authoritative.
