# Appointments (Phase 11)

First-class relational scheduling domain. Extends the existing `appointments` table used by voice booking (`/internal/scheduling`) — there is **no** parallel calendar table. CRM APIs live under `/api/admin/crm/appointments`.

Appointments are **not** Dynamic CRM EAV objects. Dynamic CRM may expose `APPOINTMENTS` as `PLATFORM_ENTITY`.

## Model

| Field | Notes |
|-------|--------|
| `appointment_number` | Tenant-scoped `APT-######` (`AppointmentNumberCounter`, `FOR UPDATE`) |
| `confirmation_code` | Legacy short code (`APT-` + hex); still returned for voice/ops |
| `customer_id` | Required; same tenant |
| `location_id` | Optional; must belong to customer |
| `service_id` | Optional FK → services; drives duration + skills |
| `job_id` | Optional FK → jobs; same customer when set |
| `assigned_technician_id` | Optional FK → technicians |
| `starts_at` / `ends_at` | `TIMESTAMPTZ` (UTC absolute instants); half-open `[start, end)` |
| `duration_minutes` | Absolute minutes between starts/ends (DST-safe; not wall-clock arithmetic) |
| `timezone` | IANA id copied from tenant business settings at create (display context) |
| `status` | See [APPOINTMENT_LIFECYCLE.md](./APPOINTMENT_LIFECYCLE.md) |
| `priority` / `is_emergency` | Emergency uses emergency business hours only |
| `idempotency_key` + `idempotency_request_hash` | Orders/Jobs parity |

## Overlap semantics

Intervals are half-open `[start, end)`:

- `10:00–11:00` and `11:00–12:00` do **not** overlap
- `10:00–11:00` and `10:30–11:30` **do** overlap

PostgreSQL `EXCLUDE USING gist` prevents concurrent double-booking for the same technician when status is in `{TENTATIVE, SCHEDULED, CONFIRMED, IN_PROGRESS}` and not archived.

**Availability is advisory; appointment create/reschedule is authoritative.**

## Timezone storage contract

| Concern | Contract |
|---------|----------|
| `appointments.starts_at` / `ends_at` | UTC `TIMESTAMPTZ` absolute instants |
| `appointments.timezone` | IANA string for UI/display context (not used for arithmetic) |
| Business hours / emergency hours | Interpreted in tenant schedule settings timezone |
| Technician schedule / breaks | Local wall-clock times in tenant business timezone |
| Technician time off | Absolute `TIMESTAMPTZ` range |
| Availability request `from_date`/`to_date` | Calendar dates in tenant business timezone |
| API serialization | ISO-8601 with offset (`…Z` or `±HH:MM`) |
| Frontend display | `Date` locale formatting; business TZ shown as metadata |

No fixed-offset assumptions. DST transitions use `zoneinfo` / `ZoneInfo`.

## Reschedule audit

`appointment_rescheduled` audit payload includes `old_starts_at`, `old_ends_at`, `starts_at`, `ends_at`. Status history is unchanged on pure reschedule (status stays the same).

## APIs

- `GET/POST /api/admin/crm/appointments`
- `GET/PATCH/DELETE /api/admin/crm/appointments/{id}`
- `POST …/transition`, `/cancel`, `/reschedule`, `/assign`, `/restore`
- `GET …/history`
- `POST /api/admin/crm/appointments/availability`
- Business hours + technician schedule endpoints under `/api/admin/crm/…`

Legacy voice: `/internal/scheduling` (same rows).

## Related

- [APPOINTMENT_LIFECYCLE.md](./APPOINTMENT_LIFECYCLE.md)
- [BUSINESS_HOURS.md](./BUSINESS_HOURS.md)
- [TECHNICIAN_AVAILABILITY.md](./TECHNICIAN_AVAILABILITY.md)
- [AVAILABILITY_ENGINE.md](./AVAILABILITY_ENGINE.md)
