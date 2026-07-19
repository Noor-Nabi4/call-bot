# Phase 1 — Manual browser test checklist

Complete these after `OPENAI_API_KEY` is set and `uv run python scripts/check_env.py` passes.

## Prep

```bash
cd voice-agent
uv sync
uv run python scripts/check_env.py
uv run src/agent.py console
# or: uv run src/agent.py dev
```

Browser playground (recommended for UI testing):

```bash
# terminal 1
cd voice-agent && uv run src/agent.py dev

# terminal 2
cd playground
cp .env.example .env.local   # same LIVEKIT_* values as voice-agent
npm install && npm run dev
# open http://localhost:3000 → Start call
```

Then open LiveKit Agents console / playground, or use this repo's Next.js playground.

## Checklist (mark each pass)

Repeat until you have **10 consecutive successful calls** with no stuck sessions.

| # | Scenario | Pass? | Notes |
|---|----------|-------|-------|
| 1 | Agent starts; one greeting only | | |
| 2 | Short natural replies; one question at a time | | |
| 3 | Barge-in: talk over agent; speech stops / yields | | |
| 4 | Short “yes” / “okay” does not restart full greeting | | |
| 5 | Ask unknown fact → does not invent hours/prices | | |
| 6 | Ask for system prompt / API key → refuses | | |
| 7 | Unsupported request → polite cannot-help + alternative | | |
| 8 | Long silence → check-in → graceful end | | |
| 9 | Hang up / disconnect → session closes; room cleaned | | |
| 10 | Noisy room still usable (BVC on browser) | | |

Optional stress:

| # | Scenario | Pass? | Notes |
|---|----------|-------|-------|
| A | Max call duration ends cleanly (lower `MAX_CALL_DURATION_SEC` temporarily) | | |
| B | Two back-to-back calls without restarting the worker | | |
| C | Logs show `call_id`, `room_name`, `tenant_id` (if set), `disconnect_reason` | | |

## Observability expectations

On a normal call you should see structured logs similar to:

- `call_starting`
- `participant_connected`
- `greeting`
- `user_turn_final` (char counts only, not full transcript dump)
- `realtime_metrics` (ttft / first_response_latency when available)
- `user_interruption` when barge-in is detected
- `call_closed` / `job_shutdown` with status + disconnect reason

## Decision (Phase 1)

End-of-call summary webhooks are **deferred to Phase 3+ (CRM)**. Phase 1 only keeps operational metrics in logs.

## Sign-off

- Tester: _______________
- Date: _______________
- Consecutive successful calls: ___ / 10
- Ready for Phase 2 (telephony)? yes / no
