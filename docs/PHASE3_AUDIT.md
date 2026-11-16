# Phase 3 Audit — Production Reliability & Infrastructure Hardening

**Date:** 2026-10-06  
**Scope:** Platform + voice-agent after Phase 1/2  
**Migration head before Phase 3:** `0021_phase2_outbox_storage`

## What already exists

| Area | Status | Notes |
|------|--------|-------|
| Multi-tenant / TenantContext / resolver | Done (P1) | Shared + dedicated DB strategy |
| Notification outbox + worker | Done (P2) | Claim→commit→I/O; SKIP LOCKED; retries; DLQ status |
| SMS/webhook TX safety | Done (P2) | Enqueue-only in request TX |
| Call-scope HMAC | Partial (P2) | CRM internal routes; PRODUCTION requires flag |
| Voice CRM client call-scope | Partial | `PlatformCrmClient` only |
| Object storage | Partial | Filesystem backend only; `recording_objects` |
| Recording retention | Partial | `delete_expired` deletes object then marks DB |
| SIGTERM on outbox worker | Partial | Stops claiming; no lease expiry reclaim |
| Health | Minimal | Single `/health` → `{"status":"ok"}` |
| Stripe webhooks | Done | Signature + event-id idempotency |
| Stripe signup | **Unsafe** | Customer + Checkout inside open `get_db` TX |
| Twilio purchase | **Unsafe** | Twilio + LiveKit inside open TX |
| Connect-existing | **Unsafe** | LiveKit trunk/dispatch inside open TX |
| Metrics | Minimal | In-process OutboxMetrics counters |
| DLQ replay API | Missing | Status only; no list/retry/discard |
| S3-compatible storage | Missing | |
| Liveness vs readiness | Missing | |
| Load / DR docs | Missing | |

## Gaps (Phase 3 must fix)

1. **Reusable async job / saga infrastructure** — do not overload `notification_outbox` (channel/SMS-shaped). New `async_jobs` table + shared worker.
2. **Twilio / LiveKit / Stripe provisioning sagas** — intent row + job → commit → provider → reconcile.
3. **Complete call-scope** — scheduling, knowledge, handoff clients + route enforcement.
4. **S3-compatible ObjectStorage** — private bucket, signed URLs, tenant keys.
5. **Lease reclaim** — `lease_expires_at` so crashed workers do not strand `processing` rows.
6. **Worker lifecycle** — shared graceful shutdown + bounded drain.
7. **DLQ ops + metrics** — list/retry/discard + job metrics.
8. **Health** — `/liveness` vs `/readiness` (Postgres with short timeout).
9. **Docs** — saga, worker ops, DR, load testing, production readiness.
10. **Failure tests** — sagas, storage, call-scope, lease reclaim.

## Architectural risks

- Purchase/connect currently return fully provisioned results synchronously; after saga, API returns queued/partial until worker completes (or inline post-commit runner for UX).
- Signup returns `checkout_url`; must run Stripe **after** commit (inline once + worker retry).
- Multiple workers × pool sizes can exhaust Postgres — document connection math.
- Filesystem storage is not multi-replica safe — S3/R2 required for HA.

## Proposed implementation order

1. Audit (this doc)  
2. `async_jobs` migration + enqueue/worker/lease  
3. Twilio purchase saga  
4. LiveKit connect saga  
5. Stripe signup saga  
6. Call-scope completion  
7. S3 storage + retention hardening  
8. Worker lifecycle + lease reclaim (outbox + jobs)  
9. DLQ admin + metrics  
10. Health endpoints  
11. Failure tests  
12. Ops docs + full verification  

## Implementation status (completed)

Phase 3 code landed: `async_jobs` + workers, Twilio/LiveKit/Stripe sagas, S3 storage, leases, DLQ admin, liveness/readiness, call-scope on voice internal clients, docs listed in the prompt.

Remaining operator tasks (not code): staging load run, restore drill, production EXPLAIN ANALYZE.
