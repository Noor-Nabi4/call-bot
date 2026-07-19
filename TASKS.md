# Call Bot — Complete Tasks Plan

Goal: build toward a **ServiceTitan-style field-service platform**, starting from a **reliable voice agent**, then CRM/jobs, booking, dispatch, and later ops modules.

This plan is ordered. Do not skip phases. Each phase must be stable before the next.

---

## Product north star

> A caller reaches the business by browser or phone. An AI voice agent handles the conversation naturally, looks up or creates the customer, captures the job request, books when possible, and writes real records into the system — with human handoff only when needed.

Long-term modules (ServiceTitan-like):

1. Voice / call intake  
2. CRM (customers, history)  
3. Jobs / work orders  
4. Scheduling / booking  
5. Dispatch / technicians  
6. Estimates / invoices / payments  
7. Notifications (SMS/email)  
8. Reporting / analytics  
9. Admin frontend  

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
- [ ] Browser playground verified end-to-end  
- [ ] `OPENAI_API_KEY` + LiveKit creds confirmed in `.env.local`  
- [ ] Telephony (SIP) not started  

**Rule:** no RAG, multi-agent, CRM, or booking until Phase 1 is green.

---

## Phase 0 — Repo & production hygiene

**Outcome:** clean, deployable voice worker repo.

- [ ] Confirm `.env.local` has `LIVEKIT_URL`, `LIVEKIT_API_KEY`, `LIVEKIT_API_SECRET`, `OPENAI_API_KEY`  
- [ ] Set `BUSINESS_NAME` and basic business facts in prompts (still versioned Python, not a DB)  
- [ ] Commit pending voice-agent changes (Realtime refactor + noise cancel + lockfile)  
- [ ] Ensure secrets never committed (`.env.local` gitignored)  
- [ ] Document run commands in root README (link to `voice-agent/README.md`)  
- [ ] Decide deploy target: LiveKit Cloud agent vs self-hosted worker  
- [ ] Add CI that runs unit tests on every PR (`pytest` unit suite)  

**Exit criteria**

- `uv sync` works  
- Unit tests pass without live providers  
- Agent starts with `uv run src/agent.py console` or `dev`

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

**Outcome:** real phone callers reach the same agent.

- [ ] Buy/configure phone number (Twilio or preferred carrier)  
- [ ] Create SIP trunk → LiveKit SIP  
- [ ] Configure inbound dispatch to `voice-agent`  
- [ ] Verify `BVCTelephony` path for SIP participants  
- [ ] Test: answer, interrupt, silence, hangup, busy/no-answer behavior  
- [ ] Test concurrent calls (2–3)  
- [ ] Test deploy/restart during an idle period (not mid-call first)  
- [ ] Capture caller phone number into `CallState.important_details`  

**Exit criteria**

- Inbound PSTN call talks to the same Realtime agent reliably  

---

## Phase 3 — CRM light (customer + lead)

**Outcome:** every serious call can create/update a real customer and lead/job request.

### 3.1 Data model (own DB first, or ServiceTitan API later)

Minimum tables/entities:

- [ ] `customers` (id, name, phones, email, address, created_at)  
- [ ] `calls` (id, room/job ids, customer_id, started_at, ended_at, status, disconnect_reason, metrics JSON)  
- [ ] `leads` or `job_requests` (customer_id, service_type, urgency, notes, status)  
- [ ] Migrations + repository layer (no LLM direct DB access)  

### 3.2 Voice tools (validated)

- [ ] `lookup_customer_by_phone`  
- [ ] `create_or_update_customer`  
- [ ] `create_job_request` / `create_lead`  
- [ ] Confirm critical fields aloud before write  
- [ ] Idempotency keys to prevent duplicate leads on retries  
- [ ] Structured tool errors → safe spoken fallback  

### 3.3 Call flow

- [ ] Identify caller phone (SIP) or ask for callback number (browser)  
- [ ] Lookup existing customer  
- [ ] Collect: name, address, service need, urgency, preferred time window  
- [ ] Confirm summary  
- [ ] Persist lead/job request  
- [ ] Spoken confirmation + optional reference number  

### 3.4 Integration choice (pick one)

**Option A — Own CRM**

- [ ] Postgres + API/services inside this monorepo  

**Option B — ServiceTitan (or similar) as system of record**

- [ ] OAuth / API credentials  
- [ ] Map tools to Customers + Jobs/Bookings endpoints  
- [ ] Store only call metrics locally if needed  

**Exit criteria**

- Test call creates a real customer + lead with no mock data  

---

## Phase 4 — Booking / scheduling

**Outcome:** agent can offer real slots and book appointments.

- [ ] Availability service (calendar or FSM schedule rules)  
- [ ] Tool: `get_available_slots`  
- [ ] Tool: `book_appointment` (confirm before commit)  
- [ ] Conflict handling / double-booking prevention  
- [ ] Reschedule + cancel flows  
- [ ] SMS/email confirmation (provider: Twilio/SendGrid/etc.)  
- [ ] Timezone handling  

**Exit criteria**

- Caller books a real appointment end-to-end by voice  

---

## Phase 5 — Jobs, dispatch, technicians (ServiceTitan core ops)

**Outcome:** office/ops can run jobs after intake.

- [ ] Job statuses: new → scheduled → dispatched → in_progress → completed → canceled  
- [ ] Dispatch board (web)  
- [ ] Technician assignment rules (manual first)  
- [ ] Technician mobile view (job details, checklist, notes)  
- [ ] Job completion notes back to customer record  
- [ ] Optional: agent can quote ETA / status on inbound “where is my tech?” calls  

**Exit criteria**

- One job can be created by voice and completed by a tech in the system  

---

## Phase 6 — Money (estimates, invoices, payments)

- [ ] Estimate generation (manual/ops first; voice later)  
- [ ] Invoice creation from completed jobs  
- [ ] Payment link / card processor  
- [ ] Voice: “pay my invoice” only after CRM+billing APIs exist  
- [ ] Never claim payment succeeded unless processor confirms  

---

## Phase 7 — Knowledge & support quality (optional RAG)

Only after booking/CRM are stable:

- [ ] Curated business knowledge base (hours, service areas, FAQs)  
- [ ] Retrieval tool with citations / source IDs  
- [ ] Prompt injection protections for retrieved text  
- [ ] Evaluation set for FAQ accuracy  

**Do not** build vector DB before Phase 3–4 are working.

---

## Phase 8 — Human handoff & multi-agent (only if needed)

- [ ] Warm transfer to human queue  
- [ ] Escalation rules (billing disputes, emergencies, abuse)  
- [ ] Optional specialist agents via LiveKit handoffs/tasks  
- [ ] Keep latency budget; avoid monolithic mega-prompt  

---

## Phase 9 — Admin product & analytics

- [ ] Admin login / roles  
- [ ] Customers, calls, jobs, appointments UI  
- [ ] Call metrics dashboard (answer rate, book rate, latency, handoff rate)  
- [ ] Recording/transcript retention policy (legal/compliance)  
- [ ] Audit log for tool writes  

---

## Explicit non-goals for early phases

Do **not** build these until the phase above them is done:

- Full ServiceTitan clone UI on day one  
- Multi-agent architecture for simple FAQ  
- Long-term memory across all callers without CRM identity  
- Sentiment engines / reflection loops  
- Large evaluation framework before basic booking works  
- Mock CRM “success” responses in production code  

---

## Suggested near-term task order (next 2–4 weeks)

1. [ ] Finish Phase 0 hygiene + commit current voice work  
2. [ ] Complete Phase 1 browser test checklist (10 calls)  
3. [ ] Add root README pointing at architecture + this plan  
4. [ ] Start Phase 2 telephony **or** Phase 3 CRM light (if phone number delayed, CRM can begin with browser + asked phone number)  
5. [ ] First real write tool: `create_lead` with confirmation  

---

## Decision log (fill as you go)

| Date | Decision | Choice | Why |
|------|----------|--------|-----|
| | System of record | Own DB / ServiceTitan API / other | |
| | Phone provider | Twilio / other | |
| | First paid feature | Lead capture / Booking | |
| | Vertical | HVAC / plumbing / general | |

---

## Definition of “v1 business useful”

Not “full ServiceTitan”. v1 business useful means:

> Inbound voice call → identify customer → capture job request → save real lead → confirm to caller → ops can see it in a simple admin or CRM.

Everything else is expansion.
