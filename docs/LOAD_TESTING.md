# Load Testing

**Date:** 2026-10-06 (final production readiness verification)

```text
STAGING LOAD TEST = NOT EXECUTED
REASON = no staging API/worker fleet reachable in this environment
MULTI-WORKER STRESS = NOT EXECUTED
REASON = no dual worker replicas / staging job inject path available
LOCAL CAPACITY METRICS (p50/p95/p99/RPS) = NOT MEASURED
```

Local unit/integration tests and a single-process API smoke against a restored DB are **not** capacity evidence.

## Scope

Hot paths that exist today:

- `POST /internal/crm/calls/start` / `end` (with `X-Call-Scope`)
- `GET` / list calls (admin / v1 cursor APIs)
- `POST /internal/crm/customers/lookup`
- `POST /internal/scheduling/slots` / book
- `POST /internal/knowledge/search`
- Outbox worker drain
- Async job worker drain

Do not invent endpoints.

## Tooling

Use any HTTP load tool (k6, vegeta, hey). Example k6 sketch:

```javascript
import http from "k6/http";
import { check } from "k6";

export const options = {
  vus: 20,
  duration: "2m",
  thresholds: {
    http_req_duration: ["p(95)<500", "p(99)<1500"],
    http_req_failed: ["rate<0.01"],
  },
};

export default function () {
  const res = http.get(`${__ENV.BASE_URL}/liveness`);
  check(res, { "alive": (r) => r.status === 200 });
};
```

Authenticated scenarios must supply `INTERNAL_SERVICE_TOKEN` and valid `X-Call-Scope` tokens minted with `METADATA_HMAC_SECRET`.

## Metrics to capture

- p50 / p95 / p99 latency
- throughput (rps)
- error rate
- Postgres connections / CPU
- Redis utilization (if used)
- queue depth (`async_jobs` pending + `notification_outbox` pending)
- worker processing latency (structured logs)

## Connection budget (must verify on staging)

```text
total ≈ API_replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
      + outbox_replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
      + job_replicas × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
      + admin/migration
```

Defaults in settings: pool 5 + overflow 10 = **15 connections per process**. Example safe budget for `max_connections=100`:

```text
2 API + 2 job workers + 2 outbox workers = 6 × 15 = 90 (+ admin headroom)
```

## Multi-worker checklist (staging)

1. Run ≥2 job worker replicas.
2. Enqueue enough jobs to force concurrent claim.
3. Confirm `FOR UPDATE SKIP LOCKED` — one job not processed twice concurrently.
4. Kill worker A mid-lease → wait lease expiry → worker B reclaims → completes.
5. Confirm retries, DLQ, and graceful SIGTERM drain.

**Not executed in this verification environment.**

## Assumptions

Document for each run: hardware, replica counts, pool sizes, whether DB is local Docker or managed, seed data size.
