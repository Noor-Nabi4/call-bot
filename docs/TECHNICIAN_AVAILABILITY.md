# Technician Availability (Phase 11)

Extends existing `technicians` — no duplicate staff table.

## Tables

| Table | Purpose |
|-------|---------|
| `technician_schedule_periods` | Per-day work windows (`day_of_week` 0=Mon…6=Sun, `open_time`/`close_time`) |
| `technician_breaks` | Recurring daily breaks |
| `technician_time_off` | Absolute `[starts_at, ends_at)` vacation/sick/etc. |
| `skills` / `technician_skills` / `service_required_skills` | Capability matching |
| `service_areas` / `technician_service_areas` | Deterministic geo match (`POSTAL_CODE`/`CITY`/`REGION` vs customer location) |

## Intersection rule

Availability for a technician is:

```text
Business hours (or emergency hours)
  ∩ Technician schedule (or business hours if tech has no schedule rows)
  − Breaks
  − Time off
  − Active appointments
  ∩ Skills (all required)
  ∩ Service area (if location supplied and tech has areas)
```

## Permissions

`appointments.technician_schedule.read|update` for schedule/breaks/time-off/skills/areas management.
