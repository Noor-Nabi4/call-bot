# Jobs (Phase 10)

First-class relational field-service Job domain. Connects Customer → Job → Technician, with optional links to a Service (pricebook catalog), a Customer Location, and the Appointment/Lead/Call that originated the job.

Jobs are **not** Dynamic CRM EAV / custom objects. Dynamic CRM may expose `JOBS` as `PLATFORM_ENTITY` for navigation/custom fields only.

Jobs extends the existing `jobs` table used by the voice-platform legacy dispatch/tech UI (`/api/jobs`) — there is **no** parallel `work_orders` table. The legacy endpoints and the Phase 10 CRM endpoints (`/api/admin/crm/jobs`) read and write the same rows; `callbot_platform.jobs.errors` re-exports the shared status/constants helpers from `callbot_platform.crm.jobs.constants` so both layers stay consistent.

## Schema

### `jobs`

| Field | Notes |
|-------|--------|
| `id`, `tenant_id` | Tenant-scoped PK |
| `job_number` | Human-readable `JOB-######`, tenant-unique, concurrency-safe (`JobNumberCounter`, `SELECT … FOR UPDATE`) |
| `reference_code` | Short random code (`JOB-XXXXXX`), distinct from `job_number`; predates Phase 10 and kept for legacy ops UI compatibility |
| `customer_id` | **Required** FK → `customers` (RESTRICT) |
| `location_id` | Optional FK → a location owned by the same customer (cross-customer locations are rejected) |
| `service_id` | Optional FK → `services` (pricebook catalog) |
| `appointment_id`, `lead_id`, `call_id` | Optional provenance FKs — set when a job is created from the voice agent's booking flow |
| `assigned_technician_id` | Optional FK → `technicians` |
| `status` | Lifecycle status (see [JOB_LIFECYCLE.md](./JOB_LIFECYCLE.md)) |
| `priority` | `LOW \| MEDIUM \| HIGH \| URGENT`, default `MEDIUM` |
| `service_type` | Free-text label (kept even when `service_id` is set, for display/history) |
| `description` | Optional, max 8000 chars |
| `scheduled_starts_at`, `scheduled_ends_at` | Optional schedule window |
| `checklist` | JSON list of `{id, label, done}`; seeded from `DEFAULT_CHECKLIST` on create |
| `completion_notes`, `completed_at` | Set when transitioning to `COMPLETED` |
| `cancelled_at` | Set when transitioning to `CANCELLED` or `NO_SHOW` |
| `idempotency_key` | Tenant-unique create idempotency |
| `idempotency_request_hash` | SHA-256 fingerprint of material create fields (Orders parity); same key + different payload → `idempotency_conflict` |
| `archived_at` | Soft archive |

### `job_notes`

Free-text notes attached to a job (`body`, `author_user_id`, `archived_at`). The transition service also auto-writes a `"Completed: …"` note when a job is marked `COMPLETED`.

### `job_attachments`

Uploaded files (filename, content type, size, tenant-prefixed object storage key: `tenants/{tenant_id}/jobs/{job_id}/attachments/{uuid}.{ext}`). Object keys are **server-generated** — client filenames never control storage paths (path segments like `../` are stripped from the display filename only).

Validation:

- Max size `15 MiB` (`ATTACHMENT_MAX_BYTES`); empty files rejected
- Allowed MIME: `application/pdf`, `image/jpeg|png|webp|gif`, `text/plain`
- Declared MIME must match magic-byte / content sniff
- Downloads use short-lived private/signed URLs after tenant + RBAC checks (`jobs.attachments.read`)

**Cross-system residual risk:** storage `put` happens before the DB insert. If the DB write fails, the service best-effort deletes the object. If that cleanup also fails, an orphan object may remain until ops garbage collection — documented residual risk, not pretended 2PC atomicity.

### `job_status_history`

Append-only status events (`from_status`, `to_status`, `changed_by`, `reason`). Also surfaced in the customer timeline (see [CUSTOMER_TIMELINE.md](./CUSTOMER_TIMELINE.md)) as `JOB_SCHEDULED`, `JOB_DISPATCHED`, `JOB_COMPLETED`, etc.

### `job_number_counters`

Per-tenant monotonic sequence (`FOR UPDATE`), same pattern as `order_number_counters`.

## Idempotency

Create supports `Idempotency-Key` (header) or `idempotency_key` (body field):

- Same key + same material payload fingerprint → the original Job is returned (no duplicate row, no duplicate `job_number` allocation, no duplicate audit)
- Same key + **different** material payload → `idempotency_conflict` (409); the existing Job is not mutated
- Concurrent same-key creates → exactly one Job is persisted; the losing request's `INSERT` hits the `uq_jobs_tenant_idempotency` unique constraint inside a `SAVEPOINT` (`session.begin_nested()`), and the handler re-queries for the winning row (and re-checks the fingerprint)

Material fingerprint fields (`job_create_fingerprint`): customer, service, service_type, location, description, priority, technician, schedule window, appointment/lead/call provenance, initial status. Actor and wall-clock timestamps are excluded.

The `Job(...)` object must be constructed and `session.add()`'d **inside** the `begin_nested()` block (not before it). If it is added before the savepoint, a rolled-back savepoint leaves the pending object registered on the outer transaction; the next autoflushed query re-attempts the same failed `INSERT` and raises `PendingRollbackError` instead of recovering. This was fixed in Phase 10 (`JobService.create()`) and is covered by `tests/test_jobs_pg_concurrency.py::test_duplicate_idempotency_key_create` against a real Postgres instance.

## Mutation rules

| Status | Description / service / location / priority / schedule editable via `PATCH`? |
|--------|------------------------------|
| NEW, SCHEDULED, CONFIRMED | Yes (`EDITABLE_STATUSES`) |
| DISPATCHED+ | No (field details are frozen once dispatch starts) |

Status cannot be set via `PATCH` — use `POST …/transition`. Job creation only allows `status` of `NEW` or `SCHEDULED`.

## APIs

Admin base: `/api/admin/crm/jobs`

- `GET/POST /jobs` (`Idempotency-Key` header supported on create)
- `GET/PATCH/DELETE /jobs/{id}` (DELETE = archive)
- `POST /jobs/{id}/restore`
- `POST /jobs/{id}/assign` (`{"technician_id": "<uuid> | null"}` — null unassigns)
- `POST /jobs/{id}/transition` (`{"to_status": ..., "reason": ..., "completion_notes": ...}`)
- `GET /jobs/{id}/history`
- `GET/POST /jobs/{id}/notes`, `PATCH/DELETE /jobs/{id}/notes/{note_id}`
- `GET/POST /jobs/{id}/attachments` (multipart `file` field), `DELETE /jobs/{id}/attachments/{attachment_id}`

Search filters (DB-side): job number/reference code, customer, technician, service, location, status, priority, scheduled date range. Keyset cursor pagination (max 200).

Legacy ops base (unchanged, still backed by the same `jobs` table): `/api/jobs`, `/api/jobs/{id}/assign`, `/transition`, `/checklist`, `/notes` — used by the Dispatch board (`/dispatch`) and the Technician mobile shell (`/tech`).

## RBAC

Permission keys: `jobs.read|create|update|delete|assign|transition`, `jobs.notes.read|create|update|delete`, `jobs.attachments.read|create|delete`.

| Role | Grant |
|------|-------|
| Owner / Admin | All job permissions (`SCOPE_ALL`, via `all_permission_keys()`) |
| Manager, Dispatcher | All job permissions, `SCOPE_ALL` — full CRUD, assign, transition, notes, attachments |
| CSR | `jobs.read/create/update`, `jobs.notes.read/create/update`, `SCOPE_ALL` — no delete, assign, transition, or attachments |
| Technician | `jobs.read/update`, `jobs.notes.read/create`, `jobs.attachments.read/create`, `SCOPE_ASSIGNED` — only on jobs assigned to them; no assign/transition/delete |
| AI Agent (voice) | `jobs.read/create/update`, `jobs.notes.read/create`, `SCOPE_ALL` — **not** delete, assign, transition, notes.update/delete, or attachments |

Scoped grants (`SCOPE_ASSIGNED`) fail closed without a `ResourceContext`. Every job-id-scoped endpoint fetches the job first (so a Technician gets `404` on another technician's job, not `403`) and then checks permission with a `ResourceContext(assigned_technician_user_id=...)` resolved from the job's `assigned_technician_id` — mirroring the legacy `/api/jobs` resource-aware checks.

## Tenant isolation

All queries filter `tenant_id` from the authenticated session/job row. Cross-tenant customer/service/location/technician references fail closed (`404`/`customer_not_found`/`technician_not_found`), and cross-tenant job IDs resolve to `404` for every sub-resource (notes, attachments, history, transition, assign).

## Related docs

- [JOB_LIFECYCLE.md](./JOB_LIFECYCLE.md)
- [JOB_ASSIGNMENT.md](./JOB_ASSIGNMENT.md)
- [CUSTOMER_TIMELINE.md](./CUSTOMER_TIMELINE.md)

## Known limitations

- No Scheduling/Dispatch optimization engine, Invoices, Payments, Estimates, or Equipment tracking — those remain gated behind the Phase 4 staging gate (`docs/PRODUCTION_READINESS.md`)
- Attachments are stored via the existing object storage abstraction (filesystem in dev/tests); MIME sniff + size limits apply; no virus scanning or image processing
- Attachment upload is not a distributed transaction: storage-then-DB with best-effort orphan delete on DB failure (residual orphan risk if cleanup fails)
- `reference_code` and `job_number` are both present for backward compatibility with the pre-Phase-10 legacy ops UI; new integrations should prefer `job_number`

## Staging status

```text
LOCAL: VERIFIED (full pytest suite — 437 passed, 1 skipped — plus dedicated
       Postgres concurrency suite: tests/test_jobs_pg_concurrency.py, 10/10 passed
       against a real local Postgres instance; EXPLAIN ANALYZE seeded ~8k Jobs
       across 4 tenants via bulk SQL)
STAGING MIGRATION: NOT AVAILABLE — no staging DATABASE_URL / APP_ENV=staging
STAGING RBAC RECONCILE: NOT EXECUTED — blocked on staging
STAGING SMOKE: NOT EXECUTED — blocked on staging
PRODUCTION: NOT EXECUTED — .env.production is ENVIRONMENT=production; intentionally not touched
```

Blockers before STAGING VERIFIED:

1. Provide a labeled staging database + API (not production Supabase)
2. Commit/deploy migrations `0039_jobs` and `0040_jobs_hardening`
3. Run `alembic upgrade head` on staging only
4. Reconcile RBAC (`POST /api/admin/organization/reconcile` or `reconcile_system_roles_for_tenant`) so the new `jobs.delete`, `jobs.transition`, `jobs.notes.*`, `jobs.attachments.*` permission keys attach to existing tenants' system roles
5. Execute Jobs CRM smoke + negative/RBAC matrix on staging

Production readiness remains **BLOCKED** until staging verification completes.
