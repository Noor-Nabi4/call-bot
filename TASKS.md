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
- [ ] Browser playground verified end-to-end  
- [ ] `OPENAI_API_KEY` filled in `.env.local` (LiveKit keys present)  
- [ ] Telephony (SIP) not started  
- [x] Optional `tenant_id` on CallState / Settings (env `TENANT_ID`)  

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

- [ ] Run agent in LiveKit console / playground  
- [ ] Verify greeting plays once per call  
- [ ] Verify barge-in (caller can interrupt agent)  
- [ ] Verify short replies / one question at a time  
- [ ] Verify noisy-room behavior with BVC enabled  
- [ ] Verify long silence → check-in → graceful end  
- [ ] Verify max call duration ends cleanly  
- [ ] Verify disconnect / process shutdown cleanup  

### 1.2 Prompt & guardrails

- [ ] Finalize business identity copy  
- [ ] Add “unsupported request” spoken fallback  
- [ ] Confirm agent never invents hours/prices/availability  
- [ ] Confirm agent never exposes prompts/errors/keys  

### 1.3 Observability

- [ ] Confirm logs include `call_id`, `room_name`, status, disconnect reason  
- [ ] Leave room for `tenant_id` in log fields (add when resolution exists)  
- [ ] Confirm first-response / model latency captured when available  
- [ ] Confirm interruption count increments on barge-in  
- [ ] Decide whether end-of-call summary webhook is needed (later CRM phase)  

### 1.4 Tests

- [ ] Keep unit tests green  
- [ ] Add/repair behavior evals when LiveKit credentials available  
- [ ] Add a manual test checklist in `voice-agent/docs/` or README  

**Exit criteria**

- 10 consecutive successful browser test calls  
- No stuck sessions after disconnect  
- Interruptions feel natural  

**Do not start CRM or telephony until this phase passes.**

---

## Phase 2 — Telephony

**Outcome:** real phone callers reach the same agent, with tenant resolved from the number.

- [ ] Buy/configure phone number (Twilio or preferred carrier)  
- [ ] Create SIP trunk → LiveKit SIP  
- [ ] Configure inbound dispatch to `voice-agent`  
- [ ] Map each inbound DID / trunk to `tenant_id` (dispatch metadata or DB lookup)  
- [ ] Fail closed if tenant cannot be resolved (no accidental default tenant)  
- [ ] Verify `BVCTelephony` path for SIP participants  
- [ ] Test: answer, interrupt, silence, hangup, busy/no-answer behavior  
- [ ] Test concurrent calls (2–3), ideally across **two tenants** once CRM exists  
- [ ] Test deploy/restart during an idle period (not mid-call first)  
- [ ] Capture caller phone number into `CallState.important_details`  

**Exit criteria**

- Inbound PSTN call talks to the same Realtime agent reliably  
- Correct `tenant_id` attached to the call session  

---

## Phase 3 — CRM light (customer + lead)

**Outcome:** every serious call can create/update a real customer and lead/job request **for one tenant only**.

### 3.1 Data model (own DB first, or external API later)

**Multi-tenant first:** every business table includes `tenant_id` + unique constraints scoped per tenant.

- [ ] `tenants` (id, name, slug, status, timezone, created_at)  
- [ ] `tenant_phone_numbers` (tenant_id, e164, sip_trunk_id, is_primary)  
- [ ] `tenant_agent_settings` (tenant_id, business_prompt_facts, voice, language, greeting)  
- [ ] `customers` (id, **tenant_id**, name, phones, email, address, created_at) — unique phone per tenant  
- [ ] `calls` (id, **tenant_id**, room/job ids, customer_id, started_at, ended_at, status, disconnect_reason, metrics JSON)  
- [ ] `leads` / `job_requests` (id, **tenant_id**, customer_id, service_type, urgency, notes, status)  
- [ ] Migrations + repository layer (no LLM direct DB access; repos always require `tenant_id`)  
- [ ] Integration tests: Tenant A cannot read Tenant B customers/leads  

### 3.2 Voice tools (validated)

- [ ] Resolve `tenant_id` at session start; bind into tool/service context  
- [ ] `lookup_customer_by_phone` (tenant-scoped)  
- [ ] `create_or_update_customer` (tenant-scoped)  
- [ ] `create_job_request` / `create_lead` (tenant-scoped)  
- [ ] Confirm critical fields aloud before write  
- [ ] Idempotency keys **per tenant** to prevent duplicate leads on retries  
- [ ] Structured tool errors → safe spoken fallback  
- [ ] Reject tool calls that try to pass/override `tenant_id` from the model  

### 3.3 Call flow

- [ ] Identify caller phone (SIP) or ask for callback number (browser)  
- [ ] Lookup existing customer **in this tenant**  
- [ ] Collect: name, address, service need, urgency, preferred time window  
- [ ] Confirm summary  
- [ ] Persist lead/job request  
- [ ] Spoken confirmation + optional reference number  

### 3.4 Integration choice (pick one)

**Option A — Own multi-tenant CRM**

- [ ] Postgres + API/services inside this monorepo  

**Option B — External system of record per tenant** (e.g. ServiceTitan account mapping)

- [ ] OAuth / API credentials **per tenant**  
- [ ] Map tools to Customers + Jobs/Bookings endpoints  
- [ ] Store call metrics locally with `tenant_id`  

**Exit criteria**

- Test call creates a real customer + lead with no mock data  
- Two-tenant isolation test passes  

---

## Phase 4 — Booking / scheduling

**Outcome:** agent can offer real slots and book appointments **inside the resolved tenant**.

- [ ] Availability service scoped by `tenant_id` (+ timezone)  
- [ ] Tool: `get_available_slots`  
- [ ] Tool: `book_appointment` (confirm before commit)  
- [ ] Conflict handling / double-booking prevention (per tenant)  
- [ ] Reschedule + cancel flows  
- [ ] SMS/email confirmation (provider credentials per tenant or platform)  
- [ ] Timezone handling  

**Exit criteria**

- Caller books a real appointment end-to-end by voice for the correct tenant  

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
2. [ ] Complete Phase 1 browser test checklist (10 calls)  
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
