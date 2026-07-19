# Phase 3 — CRM Light Checklist

Outcome: a serious call can create/update a **tenant-scoped** customer and lead with no mock data.

## Prerequisites

- [ ] Platform API running with Postgres (or SQLite for unit tests)
- [ ] `PLATFORM_API_URL` + `INTERNAL_SERVICE_TOKEN` on voice-agent
- [ ] Tenant resolved (browser metadata or SIP DID from Phase 2)

## Happy path (browser or SIP)

- [ ] Start call → tenant resolves → greeting
- [ ] Agent asks for / uses phone → `lookup_customer_by_phone`
- [ ] Collect name, address, service need, urgency, preferred window
- [ ] Agent speaks summary → caller says yes
- [ ] `create_or_update_customer` then `create_lead` succeed
- [ ] Agent reads `reference_code` aloud
- [ ] `calls` row started and ended in platform DB

## Isolation

- [ ] Tenant A customer phone not visible to Tenant B lookup
- [ ] Lead get with wrong tenant_id returns 404 / not found
- [ ] Tools never accept model-supplied `tenant_id`

## Safety

- [ ] Write tools refuse `caller_confirmed=false`
- [ ] Duplicate lead idempotency key returns same reference
- [ ] Agent does not invent prices or calendar slots (Phase 4)

## Exit criteria

- [ ] Test call creates a real customer + lead
- [ ] Two-tenant isolation tests pass (`uv run pytest tests/test_crm.py` in platform)
