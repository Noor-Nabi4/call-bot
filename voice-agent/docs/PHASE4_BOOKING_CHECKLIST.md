# Phase 4 — Booking / scheduling checklist

## Prerequisites

- [ ] Phase 3 CRM working (customer upsert + lead tools)
- [ ] Platform API running with migrated DB (`alembic upgrade head` includes `0003_scheduling`)
- [ ] Voice agent + playground configured with `PLATFORM_API_URL` and `INTERNAL_SERVICE_TOKEN`
- [ ] Tenant has timezone set (default UTC; prefer a real IANA zone like `America/Los_Angeles`)

## Automated

- [ ] `cd platform && uv run pytest tests/test_scheduling.py`
- [ ] `cd voice-agent && uv run pytest tests/test_scheduling_tools.py`

## Operator E2E (voice)

- [ ] Resolve to a known tenant (web playground with signed metadata, or SIP DID)
- [ ] Caller provides name + phone; agent saves customer
- [ ] Caller asks to book; agent calls `get_available_slots` and offers real times
- [ ] Caller confirms a slot; agent books and reads back confirmation code (`APT-…`)
- [ ] Platform DB shows `appointments` row for that `tenant_id` / `customer_id`
- [ ] `notification_outbox` has SMS row (sent if Twilio configured, else skipped/failed) and email pending if customer email set
- [ ] Reschedule to another offered slot; confirmation code unchanged; times updated
- [ ] Cancel; slot becomes available again on next `get_available_slots`
- [ ] Second tenant cannot see or modify the first tenant’s appointment

## Notes

- Capacity is one concurrent booking per tenant (Phase 5 adds technicians).
- Email is outbox-only in Phase 4 (no Resend/SendGrid send).
- Default hours: Mon–Fri 09:00–17:00 in tenant timezone; override via `tenant_schedule_settings`.
