# Appointment Lifecycle (Phase 11)

Appointment status represents the **scheduled engagement**. Job status remains separate (work execution).

## Statuses

```text
TENTATIVE → SCHEDULED → CONFIRMED → IN_PROGRESS → COMPLETED
                └──────────┬──────────┘
                           ↓
                      CANCELLED / NO_SHOW
```

Canonical values are UPPERCASE. Legacy voice aliases (`scheduled`, `canceled`) normalize on input.

## Transitions

Enforced only via `AppointmentTransitionService` / `POST …/transition` (or `/cancel`). `PATCH` cannot set `status`.

Invalid transitions fail closed: no mutation, no history row, no success audit.

## Active booking set

These statuses reserve technician time (availability + PG exclusion):

```text
TENTATIVE, SCHEDULED, CONFIRMED, IN_PROGRESS
```

Cancelled / completed / no-show / archived do not block slots.

## History

`appointment_status_history` is append-only (`from_status`, `to_status`, `changed_by`, `reason`).

Reschedule does **not** append a status-history row (status unchanged). Time-window changes are recorded on the telephony audit event `appointment_rescheduled` with old/new starts/ends.

## Terminal hardening

`COMPLETED`, `CANCELLED`, and `NO_SHOW` have no outgoing transitions. Archived appointments cannot transition. Cancelled / completed / no-show do not participate in the exclusion constraint and do not block availability.
