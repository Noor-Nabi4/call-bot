# RBAC Legacy Authorization Audit

**Updated:** Task 1.3.3 final verification  
**Scope:** Remaining `user.role` / JWT role / `require_ops_roles` usage after reconciliation + frontend permission migration.

## Summary

| Classification | Status |
| --- | --- |
| AUTHORIZATION (API / backend) | **0** — routes use permissions |
| AUTHORIZATION (frontend UX gates) | **0** — `useAuth({ permission })` / `hasPermission` |
| COMPATIBILITY | JWT + `tenant_users.role` + serialize + legacy sync |
| DISPLAY | Profile / user menu show `user.role`; roles list for labels |
| TEST FIXTURE / SEED | Creating users with `role=` |
| FALSE POSITIVE | Docs, comments, `role ===` on **target member legacy field** in team settings |

**Unauthorized role-string checks for access control:** **0**.

---

## Backend (Tasks 1.3.1 / 1.3.2 / 1.3.3)

Deprecated helpers `require_ops_roles` / `require_entitled_ops_roles` remain in `api/deps.py` for import compatibility; **no route uses them**.

`AuthorizationService.resolve_member_permissions` uses **member_roles → role_permissions only**. Legacy `tenant_users.role` does **not** grant access.

---

## Frontend (Task 1.3.3)

| Former pattern | Replacement |
| --- | --- |
| `useAuth({ roles: ["admin"] })` | `useAuth({ permission: "…" })` + `ForbiddenState` |
| `navFor` filtered by `item.roles` | `item.permission` + `hasPermission` |
| `user.role === "technician"` shell | `isTechnicianShell(user)` (roles/permissions UX) |
| Login redirect by role string | `isTechnicianShell(user)` |

Backend remains authoritative; hiding nav or showing Forbidden is UX only.

---

## COMPATIBILITY_ONLY (allowed)

| Location | Classification |
| --- | --- |
| `tenant_users.role` column | COMPATIBILITY |
| `AuthRepository._serialize_user` | SERIALIZATION |
| `create_session_token(..., role=)` | COMPATIBILITY |
| `LEGACY_ROLE_MAP` / `SYSTEM_TO_LEGACY` | COMPATIBILITY |
| `sync_legacy_primary_role` / seed backfill | SEED |
| Team settings legacy role column / `role === target.role` | DISPLAY |
| Profile / user-menu `user.role` | DISPLAY |
| `require_ops_roles` definitions (unused by routes) | COMPATIBILITY (deprecated) |

---

## NON_AUTHORIZATION

| Location | Classification |
| --- | --- |
| `create_user` when `role == technician` | SEED / domain side effect (technicians row) |
| `VALID_ROLES` on invite/update | COMPATIBILITY input validation |
| Tests constructing users with `role=` | TEST |

---

## Reconciliation (Task 1.3.3)

See [`docs/RBAC_RECONCILIATION.md`](./RBAC_RECONCILIATION.md).

---

## Remaining risks

- Staging/production migration `0025` and browser E2E: **NOT EXECUTED** (no staging credentials in this environment). See [`docs/RBAC_STAGING_VERIFICATION.md`](./RBAC_STAGING_VERIFICATION.md).
- Downgrade of `0025` is lossy (drops tombstones + source).
- Session-local `rbac_authz_cache` does **not** synchronize across horizontally scaled instances; the database remains authoritative per request.
