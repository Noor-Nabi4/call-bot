# Analytics (Phase 27)

Tenant-scoped call, sales, and operations analytics for Call & Flow.

**Gate:** APPLICATION COMPLETE / STAGING SMOKE READY  
**Permission:** `analytics.read`  
**APIs:** `GET /api/admin/analytics`, `GET /api/admin/analytics/{calls|sales|operations}`  
**UI:** `/analytics` (tabs: Overview, Calls, Sales, Operations)

Existing `GET /api/admin/metrics` remains for Phase 26 dashboard KPIs.

---

## Date range contract

| Field | Semantics |
|-------|-----------|
| `preset` | `today`, `yesterday`, `last_7_days`, `last_30_days`, `this_month`, `last_month`, `custom` |
| `from_date` / `to_date` | Required for `custom` (`YYYY-MM-DD`) |
| Timezone | `ScheduleSettingsRepository.effective_timezone` (settings override → tenant.timezone → UTC) |
| Bounds | Half-open UTC interval `[starts_from, starts_to)` covering inclusive local calendar dates |
| Series days | Tenant-local calendar dates; zeros only where the aggregation genuinely has no rows |

---

## Call metrics

| Metric | Availability | Formula |
|--------|--------------|---------|
| Total calls | Available | `COUNT(calls)` with `started_at` in range |
| Answer rate | Conditional | Among ended calls **with** `disposition_code`: non-`{no_answer, abandoned}` / reviewed. **Null** when no dispositions — true PSTN answer rate needs carrier CDR |
| Missed calls | Conditional | `disposition_code == no_answer`. **Null** when no dispositions |
| Avg duration | Available | `SUM(billable duration) / ended calls` |
| Transfer rate | Available | Handoff: `metrics.handoff_requested` or `transfer_kind != none` / ended |
| AI resolution | Available | `(ended − transfers) / ended` (same as Phase 26) |

---

## Sales metrics

| Metric | Availability | Formula |
|--------|--------------|---------|
| Leads | Available | Non-archived leads created in range |
| Qualified leads | Available | Status ∈ `QUALIFIED`, `CONTACTED`, `BOOKED`, `WON` |
| Bookings | Available | Appointments created in range excluding `CANCELLED` |
| Conversion | Available | Status ∈ `BOOKED`, `WON` / all leads created in range |
| Revenue / lead | Unavailable | No lead→payment attribution |
| Revenue / call | Unavailable | No call→payment attribution |
| Product sales | Available | `SUM(order_items.line_total)` for orders not in `DRAFT`/`CANCELLED`/`REFUNDED` |

Succeeded payment totals are returned as aggregate `revenue` for context only (not attributed).

---

## Operations metrics

| Metric | Availability | Formula |
|--------|--------------|---------|
| Jobs completed | Available | `status == COMPLETED` and `completed_at` in range |
| Cancellation rate | Available | `CANCELLED` / jobs created in range with `status != NEW` |
| No-show rate | Available | Explicit `NO_SHOW` on jobs + appointments / terminal (`COMPLETED`+`CANCELLED`+`NO_SHOW`) |
| Technician utilization | Unavailable | Requires clocked available hours; schedule templates alone are not production-safe |
| Avg job duration | Conditional | Mean of `scheduled_ends_at − scheduled_starts_at` for completed jobs with both set. No `job.started_at` column |
| Avg lead response | Conditional | Mean of first `CONTACTED` activity − `lead.created_at` |

Technician table shows assigned/completed counts only; utilization column is intentionally blank.

---

## Tenant isolation & RBAC

Every query filters by server-derived `tenant_id`. Endpoints require entitled `analytics.read`.

---

## Performance notes

- Prefer SQL `COUNT`/`SUM`/`GROUP BY` for product sales and job status.
- Call/lead series for typical 30-day windows load rows in the window and aggregate in Python (indexed by `tenant_id` + timestamp).
- No new indexes added in Phase 27; existing composites on calls/leads/jobs/appointments/orders are used.
- EXPLAIN on staging is recommended before declaring PRODUCTION READY.

---

## Related

- Phase 26 dashboard KPIs: `AdminRepository.metrics_summary`
- Metric definition source of truth: `callbot_platform/analytics/definitions.py`
