# Production Readiness Scorecard

**Date:** 2026-10-06 (staging gate)  
**Branch:** `feat/tenancy-outbox-scaling`  
**Migration head (repo):** `0022_phase3_async_jobs` (single head)  
**Automated tests:** 194 passed, 1 skipped (S3 live gated)  
**compileall:** PASS  
**ruff (Phase 3 / storage / workers / call_scope + related tests):** PASS  
**ruff (full `platform/` tree):** NOT VERIFIED clean — pre-existing FastAPI `Depends(...)` B008 debt

Statuses: **VERIFIED** | **NOT VERIFIED** | **NOT EXECUTED** | **NOT AVAILABLE** | **BLOCKED**

## Staging environment preflight

```text
Staging API/worker fleet: NOT AVAILABLE
Staging managed DB / backups: NOT AVAILABLE
S3/R2/MinIO credentials: NOT AVAILABLE
Redis: NOT AVAILABLE (localhost:6379 closed)
Docker daemon: NOT AVAILABLE
Provider sandboxes (Twilio/Stripe): NOT AVAILABLE (empty keys)
Production/Supabase: PRESENT LOCALLY — NOT TOUCHED
Local Homebrew Postgres: available (used only for prior local DR; not claimed as staging)
```

## Final scorecard

| Area                  | Status         | Evidence                                                                 | Environment      |
| --------------------- | -------------- | ------------------------------------------------------------------------ | ---------------- |
| Tenant isolation      | VERIFIED       | pytest CRM/scheduling/knowledge/jobs/telephony/outbox                   | local (pytest)   |
| Call scope            | VERIFIED       | pytest missing/invalid/expired/tampered/tenant/call; `exp <= now`; prod templates enforce `REQUIRE_CALL_SCOPE=true` | local (pytest + config) |
| DB migrations         | NOT AVAILABLE  | Repo head `0022_phase3_async_jobs` confirmed; staging revision check not possible | staging missing  |
| Backup/restore        | NOT AVAILABLE  | Managed/staging backup drill not possible; prior local drill is not staging/prod RTO/RPO | staging missing  |
| Object storage        | NOT AVAILABLE  | Live S3 gated test not run; filesystem adapter verified in pytest       | staging missing  |
| Query performance     | NOT AVAILABLE  | No representative staging dataset for EXPLAIN ANALYZE                    | staging missing  |
| Cursor pagination     | VERIFIED       | `/api/admin/calls` + `/v1/calls` keyset `started_at DESC, id DESC`; pytest pages without duplicates | local (pytest) |
| Load test             | NOT EXECUTED   | No staging fleet                                                         | staging missing  |
| Multi-worker recovery | NOT EXECUTED   | Real multi-process crash/reclaim not run; lease/SKIP LOCKED covered in unit tests only | staging missing |
| Outbox                | VERIFIED       | Code + pytest: TX commit then claim (`SKIP LOCKED`), retry/DLQ/leases   | local (pytest)   |
| Async jobs            | VERIFIED       | Code + pytest: enqueue/run/idempotency/handlers (fakes)                  | local (pytest)   |
| DLQ/retry             | VERIFIED       | pytest + admin replay paths                                              | local (pytest)   |
| Twilio saga           | NOT AVAILABLE  | Live sandbox not available; fake-provider pytest only                    | no sandbox       |
| LiveKit saga          | NOT AVAILABLE  | Live sandbox smoke not executed                                          | no sandbox       |
| Stripe saga           | NOT AVAILABLE  | Test-mode keys empty; webhook/job paths mocked in pytest only            | no sandbox       |
| Health/readiness      | VERIFIED       | `/liveness` process-only; `/readiness` checks Postgres; compose healthcheck now uses `/readiness` | local + config |
| Graceful shutdown     | NOT VERIFIED   | API SIGTERM verified previously locally; worker multi-replica reclaim **NOT EXECUTED** | mixed            |
| Security              | VERIFIED       | Call-scope + production settings gate; secret heuristic scan; install path fixed | local            |
| Observability         | VERIFIED       | Structured metrics/logs for outbox/jobs (latency, counters); no full APM | code review      |
| Connection pool       | VERIFIED       | Defaults documented: pool 5 + overflow 10 = 15/process; formula recorded | code + docs      |

## Hardening applied in this gate (real defects)

1. **`deploy/install.sh` omitted `REQUIRE_CALL_SCOPE=true`** when generating `platform/.env.production` → production deploys could boot without call-scope. **Fixed.**
2. **Compose production / selfhost templates** did not pin `REQUIRE_CALL_SCOPE=true` → **Fixed**; healthcheck switched from legacy `/health` to `/readiness`.
3. **Call-scope expiry** previously used `exp < now` (token valid at exact expiry second) → already fixed to `exp <= now` with deterministic test.
4. Local gitignored `platform/.env.production` updated to include `REQUIRE_CALL_SCOPE=true` (not committed).

## Explicit non-claims

- Local RTO/RPO are **not** production or staging values.
- Pytest does **not** prove staging multi-worker or live provider behavior.
- Full-tree ruff is **not** clean.

## Phase 4

```text
NOT READY FOR PHASE 4
```

Reason: staging/infrastructure verification for migrations, backup/restore, object storage, EXPLAIN/load, multi-worker reclaim, and live provider sagas remains **NOT AVAILABLE** / **NOT EXECUTED**.

Dynamic CRM Phase 3 + Task 3.5 hardening are **locally verified** (`docs/DYNAMIC_CRM_HARDENING.md`) but do **not** close the staging gate.

**Implementation override:** Tasks 4.1–4.4 Customer CRM and Tasks 5.1–5.4 Product Catalog were built and locally tested under an explicit development override. This does **not** approve production deployment. Gate status above remains authoritative.

### Phase 9 Orders (9.5 staging gate — 2026-10-06)

```text
LOCAL Orders hardening: VERIFIED (389 pytest passed / PG concurrency 9/9 / web build)
Repo Alembic head (workspace): 0038_orders_hardening
Migration files 0037_orders + 0038_orders_hardening: PRESENT locally, UNTRACKED in git
STAGING Orders migration/RBAC/smoke: NOT AVAILABLE (no staging env)
PRODUCTION Orders migration/smoke: NOT EXECUTED (production credentials present; not touched)
Orders production readiness: BLOCKED
```

Do **not** implement Orders / Inventory ledger / Shipping / Estimates / Invoices / Payments / Memberships or other remaining Phase 4+ commerce domains until the staging gate closes (Customer CRM and Product Catalog foundations already landed under the override — see `docs/CUSTOMER_CRM.md` and `docs/PRODUCT_CATALOG.md`).

Note: Phase 9 Orders code exists locally under the same development override. **Orders is not staging-verified and not production-ready.**

### Phase 11 Appointments hardening (2026-10-07)

```text
LOCAL Appointments hardening: VERIFIED (505 pytest passed / 1 skipped; PG concurrency + EXPLAIN local)
Repo Alembic head (workspace): 0041_appointments_scheduling
STAGING Appointments migration/RBAC/smoke: NOT EXECUTED
PRODUCTION Appointments migration/smoke: NOT EXECUTED
Appointments production readiness: BLOCKED (staging/prod not executed)
```

### Phase 12 Dispatch (2026-10-07) — final consolidation

```text
LOCAL Dispatch implementation: VERIFIED
LOCAL PostgreSQL concurrency + EXPLAIN (synthetic scale): VERIFIED (local PG only)
Production-scale EXPLAIN (local synthetic dataset): VERIFIED
STAGING Dispatch migration/RBAC/smoke: NOT EXECUTED
PRODUCTION Dispatch migration/smoke: NOT EXECUTED
Repo Alembic head (workspace): 0042_dispatch
Assignment architecture: all paths → DispatchAssignmentService
Realtime: polling dispatch_events (not WebSocket)
Dispatch production readiness: BLOCKED (staging/prod not executed)
```

### Phase 13 Estimates (2026-10-07)

```text
LOCAL Estimates implementation: VERIFIED (focused + suite in report)
LOCAL PostgreSQL concurrency + EXPLAIN (synthetic): VERIFIED when PG available
STAGING Estimates migration/RBAC/smoke: NOT EXECUTED
PRODUCTION Estimates migration/smoke: NOT EXECUTED
Repo Alembic head (workspace): 0043_estimates
Invoices/Payments: intentionally not implemented
Estimates production readiness: BLOCKED (staging/prod not executed)
```

### Phase 14 AI Voice Agent — freeze / handoff (2026-10-07)

```text
Phase 14 Implementation: COMPLETE
Phase 14 Hardening: COMPLETE
Local Verification: COMPLETE
PostgreSQL Verification: COMPLETE
Performance Verification: COMPLETE
Security Verification: COMPLETE

Voice Provider Smoke: NOT EXECUTED
Staging Verification: NOT EXECUTED
Production Verification: NOT EXECUTED

Overall Production Readiness: BLOCKED
```

Reason:

```text
Live Twilio/LiveKit/OpenAI/SMS voice path has not been executed.
Staging and production deployment verification have not been executed.
```

Implementation and local verification complete; deployment verification pending.

```text
LOCAL AI tools (tests/test_ai_tools.py): VERIFIED — 22 passed
LOCAL PostgreSQL concurrency (tests/test_ai_tools_pg_concurrency.py): VERIFIED — 16 passed
LOCAL PostgreSQL performance / EXPLAIN / N+1 (tests/test_ai_tools_pg_perf.py): VERIFIED (local synthetic)
LOCAL full backend regression: VERIFIED — 576 passed, 1 skipped
LOCAL voice registration unit tests: VERIFIED
LOCAL frontend: VERIFIED — TypeScript PASS, ESLint 0 errors / 3 warnings, 42 tests, build PASS
Repo Alembic head (workspace): 0043_estimates (no Phase 14 migration; Phase 15 adds 0044_sms_agent)
Idempotency scope: tenant + tool + operation_id (not call-scoped)
Phase 14 application freeze: AI Tool Executor, registry, booking orchestration, AI RBAC, confirmation, idempotency, voice registration
```

Security verification (local):

```text
Tenant isolation: VERIFIED
RBAC: VERIFIED
IDOR: VERIFIED
Call scope: VERIFIED
Internal token: VERIFIED (config presence; secrets not logged)
Forbidden arguments: VERIFIED
Confirmation: VERIFIED
Prompt injection structural boundary: VERIFIED
Sensitive data handling: VERIFIED
Audit: VERIFIED
```

RBAC note: AI Agent permission checks use a session-scoped permission-key cache for performance. Role/permission updates via `RoleRepository` call `AuthorizationService.invalidate_tenant`, which clears the AI permission cache so revocations/grants are reflected on subsequent AI tool authorization.

Performance note (LOCAL POSTGRESQL only): product_search p95 ≈ 127 ms while SQL EXPLAIN execution ≈ 0.031 ms — known optimization candidate in the ORM/app path; product dataset was 1,000 variants (not 10k). Estimate lookup EXPLAIN: NOT EXECUTED. See `docs/AI_TOOLS.md`.

### Phase 15 AI SMS Agent — freeze / handoff

```text
Phase 15 Implementation: COMPLETE (application)
Phase 15 Hardening: COMPLETE (local)
Local Verification: COMPLETE
PostgreSQL Concurrency/Perf: see test_sms_agent_pg.py (run when PG available)

Twilio Provider Smoke: NOT EXECUTED
Staging Verification: NOT EXECUTED
Production Verification: NOT EXECUTED

Overall Production Readiness: BLOCKED
```

Reason:

```text
Live Twilio inbound SMS → AI → tools → booking → outbound delivery has not been executed.
Staging and production deployment verification have not been executed.
```

```text
LOCAL SMS tests (tests/test_sms_agent.py): VERIFIED — 16 passed
LOCAL PostgreSQL SMS concurrency + booking E2E (tests/test_sms_agent_pg.py): VERIFIED
LOCAL PostgreSQL SMS perf: VERIFIED (local) — webhook p50≈7.55ms p95≈8.27ms; 10016 messages; index ix_sms_messages_tenant_conversation_created used; EXPLAIN execution≈0.019ms
Repo Alembic head (workspace target): 0044_sms_agent
Phase 15 reuses Phase 14 AIToolExecutor (no domain fork)
Outbound: NotificationOutbox (QUEUED ≠ DELIVERED)
PROVIDER VERIFICATION BLOCKED without Twilio credentials + staging
```

See `docs/AI_SMS_AGENT.md`.

### Phase 16 Knowledge Base / RAG — freeze / handoff

```text
Phase 16 Implementation: COMPLETE (application)
Local Verification: COMPLETE
  - test_knowledge_rag.py + test_knowledge_rag_pg.py: VERIFIED
  - Phase 14/15 subset (ai_tools + sms + knowledge): 63 passed
  - Full platform pytest: 608 passed, 1 skipped
  - Frontend: eslint (warnings only), tsc, 42 tests, production build
PostgreSQL pgvector migrate on staging fleet: NOT EXECUTED
OpenAI Embedding Provider: NOT EXECUTED
Website/PDF/DOCX live ingest: NOT EXECUTED
Staging Verification: NOT EXECUTED
Production Verification: NOT EXECUTED

Overall Production Readiness: PRODUCTION BLOCKED — APPLICATION COMPLETE / FROZEN
```

```text
LOCAL knowledge RAG tests: VERIFIED
Repo Alembic head (workspace target): 0045_knowledge_rag
Shared KnowledgeRetrievalService + search_knowledge AI tool
FakeEmbeddingService used locally when OPENAI_API_KEY unset
pgvector query uses savepoint + JSON cosine fallback if column/extension missing
PROVIDER VERIFICATION BLOCKED without OpenAI + staging
```

See `docs/KNOWLEDGE_BASE.md`.

### Phase 18 Invoicing — freeze / handoff

```text
Phase 18 Implementation: COMPLETE (application)
Local Verification: COMPLETE
  - test_invoices_crm.py + test_invoices_pg_concurrency.py: VERIFIED
  - Full platform pytest: 612 passed, 1 skipped
Payment provider (Phase 19 Stripe Connect): NOT EXECUTED
Email notification delivery (live): NOT EXECUTED
Staging Verification: NOT EXECUTED
Production Verification: NOT EXECUTED

Overall Production Readiness: PRODUCTION BLOCKED — APPLICATION COMPLETE / FROZEN
```

See `docs/INVOICING.md`.

### Phase 19 Payments — freeze / handoff

```text
Phase 19 Implementation: COMPLETE (application)
Local Verification: COMPLETE with caveats (see flake note)
  - test_payments_crm.py: VERIFIED (Stripe mocked)
  - full platform pytest: 614 passed, 1 skipped, 1 flaky failure that passed on re-run
  - suite is NOT claimed 100% clean until flake root cause is classified
Stripe test-mode Checkout: NOT EXECUTED
Stripe invoice payment webhooks: NOT EXECUTED
Email/SMS delivery of payment links (live): NOT EXECUTED
Staging Verification: NOT EXECUTED
Production Verification: NOT EXECUTED

Overall Production Readiness: PRODUCTION BLOCKED — APPLICATION COMPLETE / FROZEN
```

```text
LOCAL payment tests: VERIFIED (mocked Stripe)
Repo Alembic head (workspace target): 0047_payments
Payment → InvoicePaymentService → invoice_payment_applications
Refund policy: amount_paid↓ balance_due↑ then invoice status recalculated
  (documented in docs/PAYMENTS.md — do not change silently)
Webhook: POST /webhooks/stripe/payments (signature required)
AI tools: create_payment_link, send_payment_link_sms/email, get_payment_status
PROVIDER VERIFICATION BLOCKED without Stripe test credentials + staging
OPEN BEFORE PRODUCTION: classify flaky PG failure
  (test_sms_perf_hot_paths / customer create race) as
  genuine concurrency defect vs test sync vs env contention
```

See `docs/PAYMENTS.md`.

```text
Phase 19 application implementation is frozen.

Remaining work:
- classify flaky PostgreSQL suite failure (pre-production)
- Stripe test-mode verification
- webhook endpoint registration
- staging verification
- production deployment
- production smoke testing
```

```text
Phase 16 application implementation is frozen.

Remaining work:
- provider verification (OpenAI embeddings)
- staging verification (migrate 0045, real PDF/DOCX/website, Voice/SMS smoke)
- production deployment
- production smoke testing
```

### Phase 20 Memberships — freeze / handoff

```text
Phase 20 Implementation: COMPLETE (application)
Local Verification: COMPLETE with caveats (test_memberships_crm.py; Stripe mocked/skipped for links)
Membership billing via Invoice + Checkout (Option A): application path VERIFIED in unit tests
Stripe test-mode recurring / live Checkout for memberships: NOT EXECUTED
SMS/Email membership notifications (live): NOT EXECUTED
Staging Verification: NOT EXECUTED
Production Verification: NOT EXECUTED
Performance / EXPLAIN: NOT EXECUTED

Overall Production Readiness: PRODUCTION BLOCKED — APPLICATION COMPLETE / FROZEN
```

```text
Repo Alembic head (workspace target): 0048_memberships
Billing: Membership → Invoice → PaymentService (no second ledger; no Stripe Subscriptions)
Cancel policy: cancel_at_period_end (default); upgrade/downgrade next period; no proration
AI tools: list/get/subscribe/cancel/upgrade/downgrade (confirmation on mutations)
PROVIDER VERIFICATION BLOCKED without Stripe test credentials + staging
```

See `docs/MEMBERSHIPS.md`.

```text
Phase 20 application implementation is frozen.

Remaining work:
- Stripe test-mode membership invoice Checkout verification
- staging verification (migrate 0048)
- production deployment
- production smoke testing
```

### Phase 21 Equipment / Assets — freeze / handoff

```text
Phase 21 — APPLICATION COMPLETE / FROZEN
Commit: a54f73a
Production: BLOCKED pending staging/production verification

Local Verification: COMPLETE
  - test_equipment_crm.py: PASS
  - test_equipment_pg_concurrency.py: PASS
    (partial unique index on ORM + Alembic; 8-worker same-tenant serial → 1 success / 7 serial_conflict)
  - Full backend: 628 passed, 1 skipped (verification pass)
Migration 0049_equipment: VERIFIED on PostgreSQL
  (0048→0049 upgrade, 0049→0048 downgrade, 0048→0049 re-upgrade)
  - Full alembic chain from empty DB: BLOCKED at pre-existing 0024
    (tenants.business_size ORM vs migration order) — NOT Phase 21; do not reopen in this freeze
Performance / EXPLAIN: NOT EXECUTED
Staging Verification: NOT EXECUTED
Production Verification: NOT EXECUTED

Out of freeze scope (future work only):
  AI find_equipment / get_equipment_history, dedicated edit page, performance benchmarks
```

See `docs/EQUIPMENT.md`.

```text
Phase 21 is frozen. Do not add Equipment features on this commit.

Remaining work (ops only):
- staging migration 0049
- production deployment / smoke
```

### Phase 22 Automation Engine — freeze / handoff

```text
Phase 22 — APPLICATION COMPLETE / FROZEN (local)
Migration: 0050_automations (head)
Local Verification: COMPLETE with caveats
  - test_automations_engine.py: PASS
  - test_automations_pg_concurrency.py: PASS (one execution under concurrent workers)
  - Migration 0050 upgrade/downgrade/re-upgrade from stamped 0049: VERIFIED on PostgreSQL
Performance / EXPLAIN: NOT EXECUTED
Stripe / SMS / Email / Webhook live providers: NOT EXECUTED
Staging: NOT EXECUTED
Production: NOT EXECUTED

Overall: PRODUCTION BLOCKED — APPLICATION COMPLETE / FROZEN
```

See `docs/AUTOMATIONS.md`.

```text
Out of freeze scope:
- AI workflow generation
- canvas/graph builder
- full 10k/100k/1M performance suite
```

### Phase 23 Call Intelligence — freeze / handoff

```text
Phase 23 — APPLICATION COMPLETE / FROZEN (local)
Migration: 0051_call_intelligence (head)
Local Verification: COMPLETE with caveats
  - test_call_intelligence.py: PASS (9)
  - test_call_intelligence_pg_concurrency.py: PASS (2) on PostgreSQL
  - Migration 0051 upgrade/downgrade/re-upgrade from stamped 0050: VERIFIED on PostgreSQL
  - Backend regression (excl. known hanging PG suites): 616 passed, 1 skipped
  - Frontend: tsc PASS, eslint 0 errors, next build PASS
  - Live Twilio/LiveKit recording + STT/OpenAI analysis: NOT EXECUTED
Performance / EXPLAIN / 100k segments: NOT EXECUTED
Staging: NOT EXECUTED
Production: NOT EXECUTED

Overall: PRODUCTION BLOCKED — APPLICATION COMPLETE / FROZEN
```

See `docs/CALL_INTELLIGENCE.md`.
