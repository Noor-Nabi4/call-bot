# Business Hours (Phase 11)

Stored on `tenant_schedule_settings` (existing voice scheduling settings) plus `business_holidays`.

## Timezone

IANA identifiers only (e.g. `America/New_York`). Validated server-side. Effective timezone: settings override → tenant timezone → `UTC`. Never inferred from the browser for persisted config.

## Weekly hours

JSON map `mon`…`sun` → list of `[open, close]` `HH:MM` periods. Half-open `[open, close)`:

- Adjacent periods (`09:00–12:00` + `12:00–17:00`) are **allowed**
- Overlapping periods (`09:00–12:00` + `11:00–17:00`) are **rejected**
- `open >= close` is **rejected**

### Overnight periods

`22:00–02:00` is **not supported**. Validation fails with `invalid_weekly_hours` and an explicit overnight message. Same-day periods only in this hardening pass.

## Emergency hours

`emergency_weekly_hours` uses the same shape. Normal availability never consults emergency windows. Emergency appointment / availability requests use emergency hours only. Emergency mode does **not** bypass technician conflicts, skills, service areas, or the PostgreSQL exclusion constraint.

## Holidays

`business_holidays`: tenant + date unique, optional full-day closure name. Holidays remove the day from normal (and emergency) candidate windows. Holiday dates are calendar dates in the tenant business timezone.
