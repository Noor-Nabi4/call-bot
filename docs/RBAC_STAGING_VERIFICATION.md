# RBAC Staging Verification Runbook

Use this checklist when staging credentials become available.

**Do not use this against production.**

**Do not put secrets in this document.**

---

## Prerequisites

- Staging database URL and app env available via your normal secret store
- Confirm the target host/DB name is **staging**, not production
- Follow the existing staging backup procedure before schema changes
  (see ops runbooks / `docs/PRODUCTION_DEPLOYMENT.md` backup notes as applicable)

---

## Step 1 — Confirm environment

```bash
# Example checks — use your staging env file / secret injection
echo "$DATABASE_URL"   # must point at staging
echo "$APP_ENV"        # expect staging / non-production
```

Abort if the database or environment looks like production.

---

## Step 2 — Backup

Run the **existing** staging backup procedure before migrating.

Record backup identifier/timestamp in the verification log.

---

## Step 3 — Migrate

From the platform package (adjust path/venv as your staging deploy uses):

```bash
cd platform
alembic upgrade head
```

---

## Step 4 — Confirm migration head

```bash
alembic current
```

Expected revision includes:

```text
0025_rbac_reconciliation
```

Also confirm schema:

- column `role_permissions.source`
- table `role_permission_tombstones`

---

## Step 5 — Application health

Restart/redeploy the staging platform if required, then check:

```text
/health
/readiness
```

Verify authentication (`/auth/login`, `/auth/me`) returns session user plus `roles` and `permissions`.

---

## Step 6 — Reconcile a test organization

As a member with `roles.update` on a **non-production** test tenant:

```http
POST /api/admin/organization/reconcile
```

Or run a controlled ops shell calling:

```python
reconcile_system_roles_for_tenant(session, tenant_id, actor="staging-verify")
```

Confirm response is tenant-scoped (session tenant only).

---

## Step 7 — Tombstone lifecycle on staging

On system role **Admin**, for a catalog default such as `billing.manage`:

1. Confirm grant exists (`SYSTEM_DEFAULT` or present).
2. Revoke → permission absent + tombstone present.
3. Reconcile → still absent.
4. Re-grant → `ORG_CUSTOM` + tombstone cleared.
5. Revoke again → tombstone present.
6. Reconcile → still absent.

---

## Step 8 — Role matrix

Verify authorization for:

| Actor | Expect |
| --- | --- |
| Owner | Full ownership protections; cannot lose last Owner |
| Admin | Permissions per catalog minus Owner-only grants |
| Custom role | Exactly assigned permissions; no auto system defaults |
| Technician | Scoped jobs access; fail-closed without resource context |
| AI Agent | Tool groups only when AI Agent role has tool permissions |

---

## Step 9 — Frontend

1. Login as a user **with** `customers.read` → Customers nav + page OK.
2. Login as authenticated user **without** `customers.read` → nav hidden; direct URL shows **ForbiddenState** (not login redirect).
3. Spot-check `jobs/[id]` and `agents/[id]/flow` ForbiddenState.

---

## Step 10 — Cross-tenant isolation

With Tenant A and Tenant B:

- A cannot read/modify B roles or reconcile B.
- Tombstones created for A do not appear on B system roles.
- Cross-tenant role IDs return 404/denied per API conventions.

---

## Step 11 — Record results

Capture:

```text
Date:
Operator:
Alembic head:
Health/readiness:
Tombstone lifecycle:
Reconcile idempotency:
Owner / Admin / Custom / Tech / AI:
Frontend ForbiddenState:
Cross-tenant:
Issues:
```

Update `docs/RBAC_RECONCILIATION.md` and `ADVANCED_BUILD_TASKS.md` only after these steps actually succeed.

---

## Production

```text
NOT IN SCOPE FOR THIS RUNBOOK
```

Never run `alembic upgrade`, `reconcile_all_tenants`, or permission edits against production from this checklist.
