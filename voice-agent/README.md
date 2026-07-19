<a href="https://livekit.io/">
  <img src="./.github/assets/livekit-mark.png" alt="LiveKit logo" width="100" height="100">
</a>

# Voice Agent (v1)

Production **voice-only** LiveKit agent using **OpenAI Realtime** speech-to-speech.

## Scope

Production voice agent for multi-tenant field service:

> After trusted tenant resolve, load that tenant's Agent Profile from the Platform API, compose concise tenant-aware instructions, and run OpenAI Realtime speech-to-speech with CRM / scheduling / knowledge / handoff tools scoped to that tenant only.

**Included**

- Fail-closed tenant resolve + Agent Profile fetch (`GET /internal/tenants/{id}/agent-profile`)
- Versioned prompt composition (platform safety → voice → tenant identity/rules/prefs → tools → call context)
- Concise voice policy (answer the question first; one–two sentences default)
- Short-lived profile cache keyed by `tenant_id` + `profile_version`
- Per-call `CallState` / `CallFacts` (no long-term memory unless Platform API supports it)
- Semantic VAD turn detection and barge-in
- Structured operational logs and metrics (tenant_id, profile version, tool status)

**Not used as tenant fallback**

Env `BUSINESS_*` facts are for local/console helpers and tests only. After resolve, production calls never fall back to env business configuration.

## Architecture

```text
Caller / Browser
       │
       ▼
LiveKit Room (SIP later)
       │
       ▼
LiveKit AgentSession
       │
       ▼
OpenAI Realtime Model
       │
       ▼
Audio response through LiveKit
```

## Project layout

```text
voice-agent/
├── src/
│   ├── agent.py
│   ├── config.py
│   ├── prompts/
│   ├── session/
│   └── observability/
├── tests/
├── .env.example
├── Dockerfile
└── pyproject.toml
```

## Setup

```bash
cd voice-agent
uv sync
cp .env.example .env.local
```

Fill in `.env.local`:

| Variable | Required | Purpose |
|---|---|---|
| `LIVEKIT_URL` | yes | LiveKit Cloud WebSocket URL |
| `LIVEKIT_API_KEY` | yes | LiveKit API key |
| `LIVEKIT_API_SECRET` | yes | LiveKit API secret |
| `OPENAI_API_KEY` | yes | OpenAI Realtime access |
| `BUSINESS_NAME` | no | Spoken business identity |
| `TENANT_ID` | no | Single-tenant id until multi-tenant dispatch |
| `BUSINESS_HOURS` / `BUSINESS_SERVICES` / … | no | Facts the agent may speak |

Validate without printing secrets:

```bash
uv run python scripts/check_env.py
```
## Run

Console / playground:

```bash
uv run src/agent.py console
```

Dev worker (LiveKit Cloud):

```bash
uv run src/agent.py dev
```

Production worker:

```bash
uv run src/agent.py start
```

## Tests

Unit tests (no live providers required):

```bash
uv run pytest tests/test_config.py tests/test_prompt.py tests/test_state.py tests/test_lifecycle.py tests/test_observability.py -v
```

Behavior evals (requires LiveKit credentials for inference judge models):

```bash
uv run pytest tests/test_agent.py -v
```

## Phase 1 manual verification

Follow [`docs/PHASE1_MANUAL_CHECKLIST.md`](./docs/PHASE1_MANUAL_CHECKLIST.md) for browser/console call tests (greeting, barge-in, silence, disconnect). Complete **10 consecutive successful calls** before Phase 2 telephony.
## Telephony (phase 4)

Only after browser audio is stable: Twilio SIP trunk → LiveKit SIP → this same agent. No telephony code is required for v1 browser audio.

## Docs verified

Implementation follows current LiveKit documentation for:

- [OpenAI Realtime plugin](https://docs.livekit.io/agents/models/realtime/plugins/openai/)
- [Agent sessions / userdata](https://docs.livekit.io/agents/logic/sessions/)
- [Agents + userdata state](https://docs.livekit.io/agents/logic/agents-handoffs/)
- [Update instructions/tools in place](https://docs.livekit.io/agents/logic/tools/design/)
- [Function tools](https://docs.livekit.io/agents/logic/tools/definition/)
- [Turns / interruptions](https://docs.livekit.io/agents/logic/turns/)
- [Testing & evaluation](https://docs.livekit.io/agents/start/testing/)
- [Realtime metrics](https://docs.livekit.io/reference/recipes/metrics_realtime/)
