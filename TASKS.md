# Call Bot — Complete Tasks Plan

Goal: build a **multi-tenant ServiceTitan-style field-service platform**, starting from a **reliable voice agent**, then CRM/jobs, booking, dispatch, and later ops modules.

This plan is ordered. Do not skip phases. Each phase must be stable before the next.

---

## Product north star

> Many businesses (**tenants**) use one platform. A caller reaches **their** business by browser or phone. An AI voice agent handles the conversation for that tenant only, looks up or creates the customer, captures the job request, books when possible, and writes real records into **that tenant’s** data — with human handoff only when needed.

Long-term modules (ServiceTitan-like):

1. Voice / call intake  
2. CRM (customers, history)  
3. Jobs / work orders  
4. Scheduling / booking  
5. Dispatch / technicians  
6. Estimates / invoices / payments  
7. Notifications (SMS/email)  
8. Reporting / analytics  
9. Admin frontend (per-tenant + platform super-admin)  

---

## Multi-tenancy (platform rule)

**This product is multi-tenant.** Even while Phase 1 still runs as one business, every CRM/schema/tool design must be tenant-scoped so we do not rewrite later.

### What a tenant is

A **tenant** = one business / franchise / company on the platform (e.g. “Acme HVAC”).

Each tenant owns:

- Business profile (name, hours, service area, prompt facts)  
- Customers, leads, jobs, appointments  
- Phone numbers / SIP dispatch mapping  
- Agent settings (voice, language, greeting)  
- Users/roles (owner, dispatcher, tech)  
- Billing plan (later)  

### Hard isolation rules

- Every business row includes `tenant_id`  
- Repositories/tools **always** filter by `tenant_id`  
- Resolve tenant **before** tools run (DID / SIP trunk / dispatch or room metadata) — never from caller free text alone  
- Logs/metrics include `tenant_id` + `call_id`  
- No cross-tenant customer lookup, booking, or transcript access  
- Model cannot override `tenant_id` via tool arguments  

### Tenant resolution (voice)

```text
Inbound call / room join
        │
        ▼
Resolve tenant_id
  (DID / SIP trunk / agent dispatch metadata / room metadata)
        │
        ▼
Load tenant business profile + prompts
        │
        ▼
Start AgentSession (Realtime)
        │
        ▼
All CRM/job tools scoped to that tenant_id
```

### When to implement

| When | What |
|------|------|
| Phase 0–1 (now) | Single-tenant runtime OK (`BUSINESS_NAME` env); design CallState with future `tenant_id` |
| Phase 2 (telephony) | Map each phone number / trunk → `tenant_id`; fail closed if unresolved |
| Phase 3 (CRM) | `tenants` table + `tenant_id` on all business tables + isolation tests |
| Phase 9 (admin) | Tenant signup, invites, super-admin |

**Do not** build full tenant admin UI before Phase 1 is green.  
**Do not** design CRM tables without `tenant_id`.

---

## Current status (baseline)

Already in progress under `voice-agent/`:

- [x] LiveKit Python agent worker  
- [x] OpenAI Realtime speech-to-speech  
- [x] Separated prompts  
- [x] Per-call `CallState` (active call only)  
- [x] Interruptions + semantic VAD  
- [x] Silence / max-duration lifecycle  
- [x] Structured metrics/logging  
- [x] Krisp BVC / BVCTelephony noise cancellation  
- [x] Unit tests for config, prompts, state, lifecycle  
- [x] Multi-tenant product decision recorded  
- [x] Phase 0 hygiene (README, CI, business facts, env check)  
- [x] Phase 1 code: prompts/guardrails, observability, checklist, unit+eval tests  
- [x] Next.js browser playground (`playground/`) with token + agent dispatch  
- [ ] Browser playground verified end-to-end *(manual; needs `OPENAI_API_KEY` + worker)*  
- [ ] `OPENAI_API_KEY` filled in `.env.local` (LiveKit keys present)  
- [ ] Telephony (SIP) not started  
- [x] Optional `tenant_id` on CallState / Settings (env `TENANT_ID`)  
- [x] Phase 2 platform telephony API + agent fail-closed DID resolve (PSTN operator verification pending)  

**Rule:** no RAG, multi-agent, CRM, or booking until Phase 1 is green.

---

## Phase 0 — Repo & production hygiene

**Outcome:** clean, deployable voice worker repo.

- [x] Confirm `.env.local` has LiveKit keys present; **`OPENAI_API_KEY` must be filled by operator** (validate with `uv run python scripts/check_env.py`)  
- [x] Set `BUSINESS_NAME` and basic business facts in prompts / env (`BUSINESS_HOURS`, etc.)  
- [x] Commit voice-agent Realtime refactor + noise cancel + lockfile  
- [x] Ensure secrets never committed (`.env.local` gitignored at package + repo root)  
- [x] Document run commands in root README (link to `voice-agent/README.md` + this plan)  
- [x] Decide deploy target: **LiveKit Cloud agent worker**  
- [x] Add CI that runs unit tests on every PR (`.github/workflows/voice-agent-unit-tests.yml`)  
- [x] Decide shared worker vs per-tenant workers: **shared worker**, tenant resolved at dispatch; optional `TENANT_ID` env for Phase 0/1  

**Exit criteria**

- [x] `uv sync` works  
- [x] Unit tests pass without live providers  
- [ ] Agent starts with `uv run src/agent.py console` or `dev` (requires non-empty `OPENAI_API_KEY` in `.env.local`)  

---

## Phase 1 — Voice foundation (must be rock solid)

**Outcome:** one agent, natural speech, reliable call lifecycle.

### 1.1 Browser audio

Manual verification: [`voice-agent/docs/PHASE1_MANUAL_CHECKLIST.md`](./voice-agent/docs/PHASE1_MANUAL_CHECKLIST.md)

- [ ] Run agent in LiveKit console / playground *(requires `OPENAI_API_KEY`)*  
- [ ] Verify greeting plays once per call  
- [ ] Verify barge-in (caller can interrupt agent)  
- [ ] Verify short replies / one question at a time  
- [ ] Verify noisy-room behavior with BVC enabled  
- [ ] Verify long silence → check-in → graceful end  
- [ ] Verify max call duration ends cleanly  
- [ ] Verify disconnect / process shutdown cleanup  

### 1.2 Prompt & guardrails

- [x] Finalize business identity copy  
- [x] Add “unsupported request” spoken fallback  
- [x] Confirm agent never invents hours/prices/availability (prompt + eval coverage)  
- [x] Confirm agent never exposes prompts/errors/keys (prompt rules)  

### 1.3 Observability

- [x] Logs include `call_id`, `room_name`, status, disconnect reason  
- [x] `tenant_id` included in correlation / metrics fields when set  
- [x] First-response / model latency captured when Realtime metrics available  
- [x] Interruption count increments on barge-in (state + metrics sync)  
- [x] End-of-call summary webhook **deferred to Phase 3+ CRM** (not in Phase 1)  
- [x] `delete_room_on_close=True` + job shutdown callback for clean teardown  

### 1.4 Tests

- [x] Keep unit tests green (incl. observability + prompt guardrails)  
- [x] Behavior evals updated (skip without LiveKit creds; adds unsupported-booking case)  
- [x] Manual test checklist in `voice-agent/docs/PHASE1_MANUAL_CHECKLIST.md`  

**Exit criteria**

- [ ] 10 consecutive successful browser test calls *(operator)*  
- [ ] No stuck sessions after disconnect *(operator)*  
- [ ] Interruptions feel natural *(operator)*  

**Do not start CRM or telephony until this phase’s manual exit criteria pass.**

---

## Phase 2 — Telephony

**Outcome:** real phone callers reach the same agent, with tenant resolved from the number.

- [x] Hybrid Twilio architecture: Path A connect-existing + Path B platform purchase  
- [x] Platform API (`platform/`) with Postgres models, audit, encryption, idempotency  
- [x] Create SIP trunk → LiveKit SIP (inbound trunk + dispatch rule APIs)  
- [x] Configure inbound dispatch to `voice-agent`  
- [x] Map each inbound DID / trunk to `tenant_id` (signed metadata + DID + trunk)  
- [x] Fail closed if tenant cannot be resolved (no accidental default tenant for SIP)  
- [x] Verify `BVCTelephony` path for SIP participants (already branched)  
- [ ] Test: answer, interrupt, silence, hangup *(operator PSTN)*  
- [ ] Test concurrent calls (2–3) *(operator)*  
- [ ] Test deploy/restart during an idle period *(operator)*  
- [x] Capture caller phone number into `CallState.important_details`  
- [x] Manual checklist: [`voice-agent/docs/PHASE2_TELEPHONY_CHECKLIST.md`](./voice-agent/docs/PHASE2_TELEPHONY_CHECKLIST.md)  
- [x] Playground telephony wizard at `/telephony`  

**Exit criteria**

- Inbound PSTN call talks to the same Realtime agent reliably *(operator)*  
- Correct `tenant_id` attached to the call session *(operator after verification call)*  
---

## Phase 3 — CRM light (customer + lead)

**Outcome:** every serious call can create/update a real customer and lead/job request **for one tenant only**.

### 3.1 Data model (own DB first, or external API later)

**Multi-tenant first:** every business table includes `tenant_id` + unique constraints scoped per tenant.

- [x] `tenants` (id, name, slug, status, timezone, created_at)  
- [x] `tenant_phone_numbers` (tenant_id, e164, sip_trunk_id, is_primary)  
- [x] `tenant_agent_settings` (tenant_id, business_prompt_facts, voice, language, greeting)  
- [x] `customers` (id, **tenant_id**, name, phones, email, address, created_at) — unique phone per tenant  
- [x] `calls` (id, **tenant_id**, room/job ids, customer_id, started_at, ended_at, status, disconnect_reason, metrics JSON)  
- [x] `leads` / `job_requests` (id, **tenant_id**, customer_id, service_type, urgency, notes, status)  
- [x] Migrations + repository layer (no LLM direct DB access; repos always require `tenant_id`)  
- [x] Integration tests: Tenant A cannot read Tenant B customers/leads  

### 3.2 Voice tools (validated)

- [x] Resolve `tenant_id` at session start; bind into tool/service context  
- [x] `lookup_customer_by_phone` (tenant-scoped)  
- [x] `create_or_update_customer` (tenant-scoped)  
- [x] `create_job_request` / `create_lead` (tenant-scoped)  
- [x] Confirm critical fields aloud before write  
- [x] Idempotency keys **per tenant** to prevent duplicate leads on retries  
- [x] Structured tool errors → safe spoken fallback  
- [x] Reject tool calls that try to pass/override `tenant_id` from the model  

### 3.3 Call flow

- [x] Identify caller phone (SIP) or ask for callback number (browser) *(prompt + tools)*  
- [x] Lookup existing customer **in this tenant**  
- [x] Collect: name, address, service need, urgency, preferred time window  
- [x] Confirm summary  
- [x] Persist lead/job request  
- [x] Spoken confirmation + optional reference number  

### 3.4 Integration choice

**Option A — Own multi-tenant CRM** *(implemented)*

- [x] Postgres + API/services inside this monorepo (`platform/` CRM routes + repos)  

**Option B — External system of record per tenant** — deferred  

Manual checklist: [`voice-agent/docs/PHASE3_CRM_CHECKLIST.md`](./voice-agent/docs/PHASE3_CRM_CHECKLIST.md)

**Exit criteria**

- Test call creates a real customer + lead with no mock data *(operator)*  
- Two-tenant isolation test passes *(automated in `platform/tests/test_crm.py`)*  
---

## Phase 4 — Booking / scheduling

**Outcome:** agent can offer real slots and book appointments **inside the resolved tenant**.

- [x] Availability service scoped by `tenant_id` (+ timezone)  
- [x] Tool: `get_available_slots`  
- [x] Tool: `book_appointment` (confirm before commit)  
- [x] Conflict handling / double-booking prevention (per tenant)  
- [x] Reschedule + cancel flows  
- [x] SMS/email confirmation (Twilio SMS when configured; email outbox pending)  
- [x] Timezone handling  

**Exit criteria**

- Caller books a real appointment end-to-end by voice for the correct tenant *(operator — see `voice-agent/docs/PHASE4_BOOKING_CHECKLIST.md`)*  
- Automated isolation / overlap / idempotency tests pass *(in `platform/tests/test_scheduling.py`)*  

---

## Phase 5 — Jobs, dispatch, technicians (ServiceTitan core ops)

**Outcome:** tenant ops can run jobs after intake.

- [ ] Job statuses: new → scheduled → dispatched → in_progress → completed → canceled  
- [ ] Dispatch board (web) — tenant-scoped  
- [ ] Technician assignment rules (manual first)  
- [ ] Technician mobile view (job details, checklist, notes)  
- [ ] Job completion notes back to customer record  
- [ ] Optional: agent can quote ETA / status on inbound “where is my tech?” calls  

**Exit criteria**

- One job can be created by voice and completed by a tech in that tenant  

---

## Phase 6 — Money (estimates, invoices, payments)

- [ ] Estimate generation (manual/ops first; voice later)  
- [ ] Invoice creation from completed jobs  
- [ ] Payment link / card processor (tenant merchant accounts later)  
- [ ] Voice: “pay my invoice” only after CRM+billing APIs exist  
- [ ] Never claim payment succeeded unless processor confirms  

---

## Phase 7 — Knowledge & support quality (optional RAG)

Only after booking/CRM are stable:

- [ ] Curated knowledge base **per tenant** (hours, service areas, FAQs)  
- [ ] Retrieval tool filtered by `tenant_id`  
- [ ] Prompt injection protections for retrieved text  
- [ ] Evaluation set for FAQ accuracy  

**Do not** build vector DB before Phase 3–4 are working.

---

## Phase 8 — Human handoff & multi-agent (only if needed)

- [ ] Warm transfer to **tenant** human queue  
- [ ] Escalation rules (billing disputes, emergencies, abuse)  
- [ ] Optional specialist agents via LiveKit handoffs/tasks  
- [ ] Keep latency budget; avoid monolithic mega-prompt  

---

## Phase 9 — Admin product & analytics

- [ ] Admin login / roles (**tenant-scoped**; platform super-admin separate)  
- [ ] Tenant onboarding (create tenant, invite users, assign phone number)  
- [ ] Customers, calls, jobs, appointments UI (always filtered by session tenant)  
- [ ] Call metrics dashboard per tenant  
- [ ] Recording/transcript retention policy (legal/compliance), per tenant where required  
- [ ] Audit log for tool writes (`tenant_id` on every audit row)  

---

## Explicit non-goals for early phases

Do **not** build these until the phase above them is done:

- Full ServiceTitan clone UI on day one  
- Multi-tenant admin portal before Phase 1 voice is stable  
- Multi-agent architecture for simple FAQ  
- Long-term memory across all callers without CRM identity  
- Sentiment engines / reflection loops  
- Large evaluation framework before basic booking works  
- Mock CRM “success” responses in production code  
- Shared global customer table without `tenant_id`  

---

## Suggested near-term task order (next 2–4 weeks)

1. [x] Finish Phase 0 hygiene  
2. [ ] Complete Phase 1 browser test checklist (10 calls) — code ready; needs `OPENAI_API_KEY` + manual sign-off  
3. [x] Add root README pointing at architecture + this plan  
4. [ ] Start Phase 2 telephony **or** Phase 3 CRM light (CRM tables must include `tenant_id` from the first migration)  
5. [ ] First real write tool: `create_lead` with confirmation + tenant scope  

---

## Decision log (fill as you go)

| Date | Decision | Choice | Why |
|------|----------|--------|-----|
| 2026-07-19 | Tenancy | **Multi-tenant SaaS** | Many businesses on one platform (ServiceTitan-style) |
| 2026-07-19 | Tenant runtime | **Shared agent worker** + resolve tenant at dispatch | Simpler ops; Phase 0/1 optional `TENANT_ID` env |
| 2026-07-19 | Deploy target | **LiveKit Cloud agent worker** | Managed dispatch, insights; self-host later if needed |
| | System of record | Own DB / external API per tenant / other | |
| | Phone provider | Twilio / other | |
| | First paid feature | Lead capture / Booking | |
| | Vertical | HVAC / plumbing / general | |

---

## Definition of “v1 business useful”

Not “full ServiceTitan”. v1 business useful means:

> Inbound voice call for a resolved **tenant** → identify customer → capture job request → save real lead **for that tenant only** → confirm to caller → that tenant’s ops can see it.

Multi-tenant stretch goal (still not full Titan):

> Two tenants on one platform, two phone numbers, zero data leakage, each hears their own business name/prompt.

Everything else is expansion.
