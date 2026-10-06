# Load Testing

**Date:** 2026-10-06 (Phase 3.1)  
**Status:** Methodology documented. Staging load: **NOT EXECUTED** (no staging fleet in this environment). Local smoke: `GET /liveness` via TestClient in unit tests only — not capacity evidence.

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
}
```

Authenticated scenarios must supply `INTERNAL_SERVICE_TOKEN` and valid `X-Call-Scope` tokens minted with `METADATA_HMAC_SECRET`.

## Metrics to capture

- p50 / p95 / p99 latency
- throughput (rps)
- error rate
- Postgres connections / CPU
- queue depth (`async_jobs` pending + `notification_outbox` pending)
- worker processing latency (structured logs)

## Assumptions

Document for each run: hardware, replica counts, pool sizes, whether DB is local Docker or managed, seed data size.

## Executed in this phase

Local unit/integration tests only. **No staging load run was executed as part of Phase 3 code delivery.**
