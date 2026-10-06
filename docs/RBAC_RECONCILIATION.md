# RBAC Reconciliation (Task 1.3.3)

## Architecture (unchanged)

```text
permissions
    ↓
role_permissions (+ source, tombstones)
    ↓
organization_roles
    ↓
member_roles
    ↓
tenant_users   ← canonical membership (no duplicate members table)
```

System roles: Owner, Admin, Manager, Dispatcher, Technician, CSR, Accountant, AI Agent.

Permission keys: `resource.action` with scopes `ALL_ORGANIZATION | OWN | ASSIGNED | TEAM`.

Canonical defaults: `callbot_platform.rbac.catalog.default_role_permissions`.

## Reconciliation

Service: `callbot_platform.rbac.reconcile.reconcile_system_roles_for_tenant`.

Behavior:

1. Ensure permission catalog + system roles exist.
2. For each **system** role only, add missing default grants as `source=SYSTEM_DEFAULT`.
3. Skip any permission with a `role_permission_tombstones` row (intentional revocation).
4. Never modify **custom** roles.
5. Never change existing grant scopes/sources (`ORG_CUSTOM` preserved).
6. Never demote Owner / never touch Owner permissions via reconcile.
7. Idempotent: second run adds nothing.

### Tombstone lifecycle (critical)

For a system-role catalog default (example: Admin `billing.manage`):

```text
Default (SYSTEM_DEFAULT)
  → organization revokes
  → role_permission removed + tombstone created
  → reconcile → remains revoked

  → organization re-grants
  → role_permission with source=ORG_CUSTOM
  → tombstone cleared

  → organization revokes again
  → role_permission removed + tombstone recreated
  → reconcile → remains revoked
```

Invariant:

```text
Granted permission  → no tombstone for that (role_id, permission_id)
Revoked catalog default on a system role → tombstone + no role_permission
```

`ORG_CUSTOM` is **not** “harmless to drop.” An explicit remove of a system-role catalog default always tombstones, even when the prior grant source was `ORG_CUSTOM`. Custom roles are never auto-tombstoned by Admin edits to system roles.

### Upgrade (`0025_rbac_reconciliation`)

1. Add `role_permissions.source` (default `SYSTEM_DEFAULT`).
2. Create `role_permission_tombstones`.
3. **Freeze** existing gaps on system roles as tombstones (except newly created catalog keys in the same migrate).
4. Reconcile so only newly introduced catalog defaults are granted.

**Downgrade:** drops `source` column and tombstone table (lossy — intentional revocations metadata is discarded).

Operational endpoint (optional): `POST /api/admin/organization/reconcile` requires `roles.update`. Tenant always from session.

## Frontend authorization model

| Layer | Purpose |
| --- | --- |
| Backend `AuthorizationService` | Security boundary |
| `/auth/me` permissions | UX / nav / route gates |
| `hasPermission` / `useAuth({ permission })` | Hide UI / ForbiddenState |

JWT / `tenant_users.role` remain for **compatibility and display** only. They are not used for authorization.

## Owner / AI / call-scope

- Owner protection and last-owner rules unchanged in `RoleRepository`.
- AI tools still authorize via AI Agent role permissions + call-scope (fail closed).
- Scoped grants still fail closed without `ResourceContext`.

## Authorization cache

### Correct design

```text
HTTP request
  ↓
SQLAlchemy Session
  ↓
session.info["rbac_authz_cache"]
  ↓
AuthorizationService (any instance bound to that Session)
```

Why session-scoped:

- Repos invalidate via `AuthorizationService(session).invalidate_*`.
- A throwaway instance-local `_cache` made invalidation a no-op: the service that had already cached grants kept stale ALLOW results.
- Sharing the dict on `session.info` means every `AuthorizationService` for that Session sees the same cache and invalidations.

What it **does**:

- Correct within a single request/Session after role permission edits, member role assign/remove, role delete, and reconcile.

What it **does not**:

- Synchronize across horizontally scaled app instances (A/B/C).
- Survive beyond the Session lifecycle.
- Replace the database as the authorization source of truth.

On a new request, a new Session starts with an empty cache and reloads from the DB. Cross-instance consistency comes from the database, not from this cache.

## Operational recovery

1. Deploy migration `0025` (see `docs/RBAC_STAGING_VERIFICATION.md`).
2. If a tenant missed new catalog defaults after a code catalog change: `POST /api/admin/organization/reconcile` as a member with `roles.update`, or run `reconcile_system_roles_for_tenant` in a controlled ops shell.
3. Do **not** delete tombstones unless the organization intends to restore those defaults.

## Verification evidence

Local (executed during hardening):

- Tombstone lifecycle states 1–6 (`billing.manage`)
- Revoke/re-grant/revoke + custom-role isolation + cross-tenant tombstones
- Session-shared cache + cross-instance (same Session) invalidation + cross-Session isolation

Staging:

```text
STAGING MIGRATION NOT EXECUTED — credentials/environment unavailable
STAGING E2E NOT EXECUTED — credentials/environment unavailable
```

Production: **NOT TOUCHED**

Staging procedure: [`docs/RBAC_STAGING_VERIFICATION.md`](./RBAC_STAGING_VERIFICATION.md)
