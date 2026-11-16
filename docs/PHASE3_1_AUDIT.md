# Phase 3.1 Audit — Final Production Hardening

**Date:** 2026-10-06  
**Migration head:** `0022_phase3_async_jobs`  
**Tests at audit:** 187 passing

## Current state (verified in code)

| Area | Status |
|------|--------|
| Purchase / connect sagas | Async via `async_jobs` |
| Stripe signup saga | Async via `async_jobs` |
| Notification outbox | Async; leases + reclaim |
| Call-scope | CRM / scheduling / knowledge / handoff |
| Object storage | Filesystem + S3 adapter (`boto3` in deps) |
| Health | `/liveness`, `/readiness` |

## Remaining provider I/O in request handlers

| Operation | File | TX risk | Phase 3.1 action |
|-----------|------|---------|------------------|
| `release` | `telephony/services/purchase.py` | Twilio + LiveKit while `get_db` open; DB update after | **Saga** `telephony.release` |
| `search_inventory` | same | Twilio search after optional `ensure_subaccount` write | **Decouple**: require subaccount; search read-only (no writes during provider call) |
| `ensure_subaccount` | same | Provider **before** DB write | Keep; document as safe dual-write pattern |
| `assign_profile` refresh | `phone_assign.py` | LiveKit update after flush | **Saga** `telephony.refresh_dispatch` |
| `create_checkout_for_tenant` | `billing/service.py` | Stripe after flush | Use existing `stripe.checkout_provision` job |
| `create_portal_session` | same | Read then Stripe | Acceptable (no prior writes) |
| Stripe webhooks | billing | Event processing TX | Keep (async webhook ingress) |

## What can be verified locally

- Unit/integration pytest (SQLite)
- Filesystem object storage
- Lease reclaim / DLQ / call-scope / tenant isolation
- `alembic heads` / `compileall` / ruff
- Query plan inspection against SQLite/local Postgres if present

## What requires external infrastructure (NOT AVAILABLE in this environment unless configured)

| Item | Status |
|------|--------|
| Real S3/R2/MinIO put/get/signed URL | Integration test gated on env |
| Postgres backup restore drill | Procedure only |
| Staging load test | Methodology + local smoke only |
| Production EXPLAIN ANALYZE | Document plans; not executed on prod |

## Implementation status (Phase 3.1 complete)

- Release + dispatch refresh sagas on `async_jobs`
- Inventory: ensure_subaccount then commit; search read-only
- Checkout resume via `stripe.checkout_provision`
- MIME allow-list on object storage
- Gated S3 integration test (`S3_INTEGRATION_TEST=1`)
- Docs: DR/query/load/deploy updated with VERIFIED vs NOT EXECUTED

```text
pytest: 194 passed, 1 skipped (S3 live)
```
