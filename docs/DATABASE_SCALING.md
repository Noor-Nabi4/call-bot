# Database Scaling

**Date:** 2026-10-06  
**Context:** Shared multi-tenant Postgres today. Scale without premature microservices or per-tenant databases for every customer.

---

## 1. Scaling principles

1. Fix correctness (tenant isolation) before optimizing.
2. Index from measured query patterns, not guesswork.
3. Keep transactions short; move I/O to outbox/workers.
4. Partition only when volume + query patterns justify it.
5. Separate analytics from OLTP early enough to protect voice latency.
6. Dedicated DB only for enterprise tenants that need it.

---

## 2. Connection pooling

### Current target configuration

Process-wide SQLAlchemy `QueuePool`:

| Setting | Guidance |
|---------|----------|
| `pool_size` | Modest per process (e.g. 5–10) |
| `max_overflow` | Bounded burst (e.g. 10–20) |
| `pool_timeout` | Fail fast under saturation |
| `pool_recycle` | Below idle LB/DB timeouts (e.g. 1800s) |
| `pool_pre_ping` | Enabled for dropped connections |

Tune using **total** connections across the fleet:

```text
max_connections_needed ≈
  (API_replicas × uvicorn_workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW))
  + (outbox_worker_replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW))
  + (job_worker_replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW))
  + (active dedicated engines × ~2–4 each)
  + headroom for migrations / admin / analytics

Keep max_connections_needed < Postgres max_connections.
```

### Dedicated tenants

Do not open a permanent large pool for every inactive dedicated DB. Use `DedicatedEngineCache` with idle dispose (`DEDICATED_DB_IDLE_SECONDS`).

---

## 3. High-volume tables

| Table | Growth | Near-term | Later |
|-------|--------|-----------|-------|
| `calls` | High | Indexes; pagination; column discipline | Time partition; split QA/metrics |
| `call_cogs` | 1:1 with calls | Already indexed `(tenant_id, created_at)` | Archive with calls |
| `telephony_audit_events` | High | `(tenant_id, created_at)` index; retention job | Partition / cold storage |
| `notification_outbox` | Medium | Status dequeue index; worker drain | TTL delete after success |
| `telephony_idempotency_keys` | Medium | TTL cleanup | — |
| `job_notes` | Medium | Paginate by job | — |
| `stripe_webhook_events` | Platform | Unique event id | Prune old processed |

Retention settings (`tenant_retention_settings`) must drive real deletion/archival jobs once recordings/transcripts exist.

---

## 4. Pagination

All large collections:

- Require `limit` (hard cap, e.g. 200)
- Prefer **keyset/cursor** pagination for high-volume tables (`(created_at, id)` or `(started_at, id)`)
- Always filter by `tenant_id`
- Deterministic `ORDER BY`

Avoid unbounded `SELECT *` / full tenant dumps in production APIs (knowledge list was historically unbounded — must be capped).

---

## 5. Caching (Redis)

Safe/high-value:

- Agent profiles (already)
- Tenant feature flags / entitlements
- Idempotency responses (short TTL)
- Rate limits (move from in-process)

Avoid caching mutable financial ledgers or anything that can leak across tenants.

Key pattern:

```text
tenant:{tenant_id}:{resource}:{id}
```

---

## 6. Async / outbox

Move off the request/DB transaction:

```text
email, SMS retries, analytics, AI summaries, transcription,
embeddings, report generation, webhook delivery
```

Pattern:

```text
DB transaction (write business row + outbox)
  → commit
  → worker publishes/processes
  → idempotent consumer
```

Events must include: `event_id`, `tenant_id`, `event_type`, `aggregate_id`, `created_at`, `payload`.

`notification_outbox` is the existing seed; generalize to `domain_events` when multiple consumers appear.

---

## 7. Voice path budget

```text
Voice Agent → AI Tool Gateway → single domain operation
```

Forbidden on the realtime path: multi-domain fan-out, heavy analytics, large history loads, synchronous embedding writes.

---

## 8. Object storage

Large binaries (recordings, PDFs, product images, KB files) belong in object storage.

DB stores metadata only: `file_id`, `tenant_id`, `object_key`, `mime_type`, `size`, `metadata`.

---

## 9. Analytics pipeline

```text
Transactional DB → Outbox / CDC → Analytics pipeline → Analytics DB
```

Do not run warehouse-style aggregations on the primary used by voice/CRM.

---

## 10. Recommended next scaling steps (ordered)

1. ~~Drain `notification_outbox` with a worker; stop SMS inside open transactions.~~ **Done (Phase 2)**
2. ~~Call-scoped internal authorization.~~ **Done (Phase 2)** — enable `REQUIRE_CALL_SCOPE=true` in production
3. ~~Cursor pagination on admin/v1 calls.~~ **Done (Phase 2)**
4. ~~Object storage + retention sweeper for recordings.~~ **Done (Phase 2)** — filesystem backend; swap to S3 later
5. Saga for Twilio/LiveKit purchase/connect (still deferred — see `TRANSACTION_AUDIT.md`)
6. Stripe signup after-commit dual-write remediation
7. Evaluate partitioning `calls` after sustained multi-tenant volume
8. Stand up analytics store; stop OLTP report scans
9. Optional RLS for defense in depth once session `SET LOCAL` is wired

---

## 11. Anti-patterns

- One giant table for every CRM/commerce field
- Micro-table for every 2–3 columns with no query benefit
- Indexing every column “just in case”
- Premature DB-per-tenant for all customers
- External HTTP inside long DB transactions
- Analytics on the voice primary
- Cache keys without `tenant_id`
