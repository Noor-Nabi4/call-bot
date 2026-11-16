# Job Lifecycle (Phase 10)

## Status graph

```text
NEW ──────────────┬──→ SCHEDULED
                   │        │
                   │        ├──→ CONFIRMED ──┐
                   │        │                │
                   │        └──→ DISPATCHED ←┘
                   │                 │
                   │                 ├──→ EN_ROUTE ──→ ARRIVED
                   │                 │        │           │
                   │                 └──→ IN_PROGRESS ←───┘
                   │                                │
                   │                                └──→ COMPLETED

Any of {NEW, SCHEDULED, CONFIRMED, DISPATCHED, EN_ROUTE, ARRIVED, IN_PROGRESS}
                   └──→ CANCELLED

Any of {SCHEDULED, CONFIRMED, DISPATCHED, EN_ROUTE, ARRIVED}
                   └──→ NO_SHOW
```

Authoritative transitions are enforced in `JobTransitionService` (`VALID_TRANSITIONS` in `callbot_platform.crm.jobs.constants`). Invalid transitions raise `invalid_transition` and do **not** write history. `DISPATCHED → IN_PROGRESS` and `SCHEDULED → DISPATCHED` are kept as operational shortcuts so the legacy Dispatch board / Technician mobile shell (which do not use `EN_ROUTE`/`ARRIVED`/`CONFIRMED`) remain valid alongside the full field-service path.

## Semantics

| Status | Meaning |
|--------|---------|
| NEW | Created, not yet scheduled |
| SCHEDULED | Has a `scheduled_starts_at` window |
| CONFIRMED | Customer/office confirmed the appointment |
| DISPATCHED | Sent to a technician — **requires an assigned technician** |
| EN_ROUTE | Technician traveling to site — requires an assigned technician |
| ARRIVED | Technician on site — requires an assigned technician |
| IN_PROGRESS | Work underway — requires an assigned technician |
| COMPLETED | Terminal — requires non-empty `completion_notes` |
| CANCELLED | Terminal cancel from any pre-completion state |
| NO_SHOW | Terminal — customer/site no-show from a scheduled-but-not-yet-started state |

## Guard rules (enforced server-side, not just UI)

- **Field mutability**: after leaving `EDITABLE_STATUSES` (`NEW` / `SCHEDULED` / `CONFIRMED`), `PATCH` field updates raise `job_immutable` (409). Status still cannot be set via `PATCH` — use `POST …/transition`.
- **Technician required**: entering `DISPATCHED`, `EN_ROUTE`, `ARRIVED`, or `IN_PROGRESS` without `assigned_technician_id` set raises `technician_required` (409). Assign a technician first via `POST /jobs/{id}/assign`.
- **Completion notes required**: transitioning to `COMPLETED` without non-empty `completion_notes` raises `400`. On success, the service also auto-writes a `JobNote` (`"Completed: <notes>"`) and sets `completed_at`.
- **Archived jobs are frozen**: transitioning an archived job raises `job_archived` (409) — restore it first.
- **No-op transitions are idempotent**: transitioning to the job's current status returns the job unchanged (no new history row, no audit event) rather than erroring — this is what makes `test_duplicate_transition_idempotent` safe for retried webhook/UI calls.

## History

`job_status_history` is append-only. Job creation writes `from_status=NULL → <initial status>` (`NEW` or `SCHEDULED`). Rejected transitions write nothing. History rows are also projected into the customer timeline (`CUSTOMER_TIMELINE.md`) as `JOB_SCHEDULED`, `JOB_CONFIRMED`, `JOB_DISPATCHED`, `JOB_EN_ROUTE`, `JOB_ARRIVED`, `JOB_IN_PROGRESS`, `JOB_COMPLETED`, `JOB_CANCELLED`, `JOB_NO_SHOW`.

## Concurrency

Transitions load the job with `SELECT … FOR UPDATE` (`JobTransitionService.transition`). Concurrent conflicting transitions (e.g. one request moving `IN_PROGRESS → COMPLETED` while another moves the same job `IN_PROGRESS → CANCELLED`): one succeeds, the other blocks on the row lock and then re-evaluates against the now-updated `current` status, raising `invalid_transition`. Verified against real Postgres in `tests/test_jobs_pg_concurrency.py::test_concurrent_status_transition_serialized` (exactly 1 success / 1 `invalid_transition` failure, never both succeeding or both failing).

## Status case normalization

`normalize_status()` accepts any case/separator variant (`"in_progress"`, `"IN-PROGRESS"`, `"in progress"` all resolve to `"IN_PROGRESS"`) and legacy aliases (`"CANCELED"` → `"CANCELLED"`, `"ENROUTE"` → `"EN_ROUTE"`, `"INPROGRESS"` → `"IN_PROGRESS"`). The API always **returns** the canonical uppercase value — frontend code must compare against uppercase literals (see `web/src/lib/api/job-constants.ts`), not the lowercase strings used by the pre-Phase-10 legacy ops UI.
