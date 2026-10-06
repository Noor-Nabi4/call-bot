# RBAC Legacy Authorization Audit (Task 1.3.1)

**Date:** 2026-10-06  
**Scope:** Remaining `user.role` / `require_ops_roles` authorization after Task 1.3.

## Summary

| Classification | Count (before) | Count (after) |
| --- | ---: | ---: |
| MUST_MIGRATE | 90+ route gates + jobs role branches | **0** |
| COMPATIBILITY_ONLY | JWT/UI/serialize/seed map | documented below |
| NON_AUTHORIZATION | invite creates Technician row, VALID_ROLES validation | kept |
| FALSE_POSITIVE | comments / docs / tests fixtures | n/a |

**Authorization usage of legacy role checks:** **0** remaining in API route gates.

Deprecated helpers `require_ops_roles` / `require_entitled_ops_roles` remain in `api/deps.py` only for import compatibility; **no route uses them**.

---

## MUST_MIGRATE → Migrated

| Area | Legacy gate | Permission(s) |
| --- | --- | --- |
| Jobs list/get/update | `user.role == technician` + OPS roles | `jobs.read` / `jobs.update` + `ResourceContext` |
| Jobs create/assign | `require_entitled_ops_roles(admin, dispatcher)` | `jobs.create` / `jobs.assign` |
| Technicians | OPS roles | `technicians.read` / `technicians.manage` |
| Tech location | `user.role != technician` | `jobs.update` + self ASSIGNED context |
| Billing subscription/usage | `require_ops_roles(admin)` | `billing.read` |
| Billing checkout/portal | `require_ops_roles(admin)` | `billing.manage` |
| Admin CRM lists | admin/dispatcher | `customers.read`, `calls.*`, `appointments.read`, `analytics.read` |
| Admin queue/supervisor | admin/dispatcher | `calls.read`, `handoff.read` / `handoff.manage` |
| Admin users | admin | `team.read` / `team.manage` |
| Admin retention/audit | admin | `organization.read` / `organization.update` |
| Admin agent settings | admin | `ai.read` / `ai.configure` |
| Admin COGS | admin | `billing.read` |
| Knowledge ops | admin/dispatcher | `knowledge.read` / `knowledge.manage` |
| Handoff ops | admin/dispatcher | `handoff.read` / `handoff.manage` |
| Automations | admin | `automations.read` / `automations.manage` |
| Branding | admin | `branding.manage` |
| API keys | admin | `api_keys.manage` |
| Agent profiles / marketplace | admin | `ai.read` / `agents.manage` |
| Phone numbers | admin | `phones.manage` |
| Async job DLQ | admin | `automations.manage` |
| Organization (already 1.3) | — | `organization.*`, `team.*`, `roles.*` |

Catalog adjustments to preserve prior access:

- Admin system role includes `billing.manage` (Owner still exclusive for `api_keys.manage` grants).
- Dispatcher gains `technicians.manage` and `knowledge.manage`.

---

## COMPATIBILITY_ONLY (allowed)

| Location | Why |
| --- | --- |
| `tenant_users.role` column | JWT claim + UI legacy select |
| `AuthRepository._serialize_user` / membership serialize | response field |
| `create_session_token(..., role=)` | JWT payload |
| `LEGACY_ROLE_MAP` / `SYSTEM_TO_LEGACY` | sync display role |
| `AuthorizationService` fallback when **no** `member_roles` | bootstrap edge case only |
| `sync_legacy_primary_role` / seed backfill | migration |
| `web` settings team “Legacy role” column | UX |
| Frontend `useAuth({ roles: ["admin"] })` | UX gate only; backend authoritative |

---

## NON_AUTHORIZATION

| Location | Why |
| --- | --- |
| `create_user` / update when `role == technician` | creates `technicians` row (domain side effect) |
| `VALID_ROLES` on invite/update bodies | input validation of legacy string field |
| Tests constructing users with `role=` | fixtures |

---

## Auth repository last-admin

Previously counted `tenant_users.role == admin`.  
Now counts active members with **Owner** or **Admin** `member_roles` (`_count_privileged_members`).

---

## Task 1.3.2 fail-closed scopes

`AuthorizationService.has_permission`:

- `ALL_ORGANIZATION` → allow without resource; with resource require `resource.tenant_id == tenant_id`
- `OWN` / `ASSIGNED` / `TEAM` only → **DENY** if `resource is None` or required fields missing
- List endpoints use `list_access_mode()` (`all` | `assigned` | deny) instead of treating missing context as allow

---

## Remaining risks

- Frontend still filters by JWT legacy role for page access (UX only).
- Legacy string role still synced for clients; do not delete until clients migrate.
- Background maintenance jobs remain trusted system operations (documented; not user-acting).
