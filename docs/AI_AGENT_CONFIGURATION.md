# AI Agent Configuration

Phase 30 — tenant-scoped agent profile, capabilities, transfer/escalation rules.

## Freeze status

```text
APPLICATION COMPLETE
RUNTIME FRAMEWORK VERIFIED
LIVE VOICE VERIFICATION BLOCKED
PRODUCTION BLOCKED
```

Next work is staging verification of the OpenAI Realtime / LiveKit voice path
(and ideally a real inbound Twilio → LiveKit → Realtime call) — not another
architecture phase.

> **Configuration enables capabilities. Configuration does not bypass authorization.**

## Architecture

```text
Tenant → agent_profiles (draft|active|archived)
       → capabilities (business_prompt_facts JSON)
       → enabled_tools (projected tool groups)
       → AIToolExecutor + RBAC + confirmation
       → domain services
```

Reuses existing:

- `agent_profiles` table (no parallel config tables)
- Phase 14 `AIToolExecutor` / `TOOL_SPECS`
- `TenantHandoffSettings` for transfer destinations/mode
- `TenantScheduleSettings` for canonical business hours
- Redis/versioned voice profile cache (`profile_version`)

## Agent profile

| Field | Storage | Notes |
|-------|---------|-------|
| Agent name | `assistant_name` | Spoken identity |
| Voice | `voice` | Controlled catalog (`agent_config.voices`) |
| Language | `language` / `supported_languages` | ISO-ish codes (`en`, `es`, …) |
| Tone | `tone` | Controlled catalog |
| Greeting | `greeting` | Previewed in UI; max length validated |
| Business hours (prompt) | `business_hours` + `business_hours_summary` | Prompt guidance |
| Canonical hours | `tenant_schedule_settings` | Scheduling / after-hours routing |
| After-hours behavior | `business_prompt_facts.after_hours_behavior` | take_message, offer_callback, … |
| Transfer rules | `business_prompt_facts.transfer_rules` | Boolean matrix |
| Escalation rules | `business_prompt_facts.escalation_rules` | Boolean matrix + fixed priority |
| Custom style | `custom_instructions` | Untrusted; cannot bypass tools |

## Voice catalog

OpenAI Realtime voices supported by the LiveKit Agents plugin (default `marin`).

Invalid voices are rejected on save. Voice runtime applies `profile.voice` via `RealtimeModel.update_options` **before** the greeting (OpenAI does not allow voice changes after first audio response).

## Capabilities

Registry: `callbot_platform.agent_config.capabilities`.

| Key | Tools (examples) | Modules |
|-----|------------------|---------|
| CALL_ANSWERING | (prompt) | — |
| HUMAN_TRANSFER | `request_human` | — |
| APPOINTMENT_BOOK | `create_booking`, … | APPOINTMENTS |
| APPOINTMENT_RESCHEDULE | `reschedule_appointment` | APPOINTMENTS |
| APPOINTMENT_CANCEL | `cancel_appointment` | APPOINTMENTS |
| PRODUCT_SEARCH | `search_products` | PRODUCTS |
| INVENTORY_LOOKUP | `check_inventory` | INVENTORY |
| PRICING_LOOKUP | `get_product_price`, … | — |
| LEAD_CREATE | `create_customer` | CUSTOMERS |
| LEAD_QUALIFY | … | LEADS/CUSTOMERS |
| ORDER_LOOKUP | `find_orders` | ORDERS |
| PAYMENT_LINK | `create_payment_link` | PAYMENTS |
| SMS_SEND | `send_sms` | SMS config |

Server-side: enabling a capability without its CRM module → `CAPABILITY_UNAVAILABLE`.

Executor: tool request → capability enabled? → RBAC → confirmation/idempotency → domain. Disabled → `capability_disabled` (no mutation).

## Draft / active

- `status=draft` — editable; **not** served to voice runtime (`get_voice_profile` requires `active`)
- `status=active` — used for new calls; `profile_version` bumps on update
- In-flight calls keep the snapshot already loaded into the worker

Activate: `POST /api/admin/agent-config/profiles/{id}/activate` after validation.

## APIs

| Method | Path | Permission |
|--------|------|------------|
| GET | `/api/admin/agent-config/catalog` | `agents.manage` |
| GET | `/api/admin/agent-config/profiles/{id}` | `agents.manage` |
| PUT | `/api/admin/agent-config/profiles/{id}` | `agents.manage` |
| POST | `/api/admin/agent-config/profiles/{id}/activate` | `agents.manage` |

Finer catalog keys also exist: `agent_config.read|update|activate`, `agent_capabilities.read|update`.

## UI

`/agents/[id]` — Profile → Capabilities → Hours → Transfers → Review → Phones.

## Audit

`AGENT_CONFIG_UPDATED`, `AGENT_CONFIG_ACTIVATED`, `AGENT_CAPABILITY_*`, `AGENT_TRANSFER_RULE_UPDATED`, `AGENT_ESCALATION_RULE_UPDATED`, plus existing `agent_profile_updated`.

## Runtime resolution path (framework)

```text
Incoming call
  → tenant resolve (fail closed)
  → active agent profile only (draft/archived → unavailable)
  → instructions + voice from profile
  → tool groups from enabled_tools
  → each tool invoke:
        capability (active profile)
      → RBAC
      → confirmation / idempotency (Phase 14)
      → domain service
```

Verified in automated tests (`tests/test_agent_config.py`):

- Draft profile not served to voice (`get_voice_profile` / active default only)
- Disabled appointment / inventory / SMS / payment / handoff → tool rejected
- Enabling a capability does not bypass Phase 14 confirmation
- Tenant A capabilities cannot authorize Tenant B tools

## Fail-closed

- Missing/inactive profile → voice agent ends call (`agent_profile_unavailable`)
- Draft/archived default → not resolved for voice or capability authorization
- Capability load failure → tool returns `system_unavailable` / does not execute
- No credentials stored in agent config

## Provider verification

| Layer | Status |
|-------|--------|
| Framework (catalog, APIs, executor gate, UI, runtime path unit tests) | **RUNTIME FRAMEWORK VERIFIED** |
| Live OpenAI Realtime voice swap on a real call | **NOT VERIFIED** / LIVE VOICE VERIFICATION BLOCKED |
| Real Twilio → LiveKit → Realtime inbound | **NOT VERIFIED** / PRODUCTION BLOCKED |

## LiveKit docs topics used

- OpenAI Realtime plugin voice parameter
- `RealtimeModel.update_options(voice=…)`
- Tool definition / in-place tool updates
