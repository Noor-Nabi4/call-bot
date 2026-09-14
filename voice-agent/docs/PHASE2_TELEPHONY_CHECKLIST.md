# Phase 2 — Twilio Hybrid Telephony Checklist

Outcome: real phone callers reach `voice-agent`, with fail-closed tenant resolution from DID / signed metadata / LiveKit trunk.

## Prerequisites

- [ ] LiveKit Cloud project with SIP enabled
- [ ] `LIVEKIT_SIP_HOST` from project settings (used as `sip:<host>;transport=tcp`)
- [ ] Platform Twilio master Account SID + Auth Token (Path B only)
- [ ] Postgres for `platform/` (or SQLite for local unit tests only)
- [ ] Shared secrets: `METADATA_HMAC_SECRET`, `INTERNAL_SERVICE_TOKEN`, `CREDENTIALS_ENCRYPTION_KEY`

## Run stack

```bash
# terminal 1 — platform API
cd platform && uv sync && uv run uvicorn callbot_platform.main:app --port 8000

# terminal 2 — voice agent
cd voice-agent && uv run src/agent.py dev

# terminal 3 — web (marketing + ops / phones / playground)
cd web && npm run dev
```

Docs used (verify latest via LiveKit MCP before changing SIP code):

- https://docs.livekit.io/telephony/start/providers/twilio/
- https://docs.livekit.io/telephony/accepting-calls/inbound-trunk/
- https://docs.livekit.io/telephony/accepting-calls/dispatch-rule/
- https://docs.livekit.io/reference/telephony/sip-participant/

## Path A — Connect existing Twilio number

- [ ] Create tenant via wizard or `POST /tenants`
- [ ] `POST /tenants/{id}/phone-numbers/connect` with E.164
- [ ] Platform creates LiveKit inbound trunk + dispatch rule (`agent_name=voice-agent`)
- [ ] Follow returned Twilio Elastic SIP steps (Origination URI → LiveKit; associate number)
- [ ] Do **not** paste customer Twilio Auth Token
- [ ] Confirm trunk SID (optional) → start verification
- [ ] Place inbound call → number becomes `active` / `verified`

## Path B — Purchase via platform

- [ ] Ensure Twilio subaccount for tenant
- [ ] Search inventory (real Twilio results + pricing when available)
- [ ] Purchase with `confirm=true` + `Idempotency-Key`
- [ ] Confirm Twilio trunk association + LiveKit trunk/dispatch persisted
- [ ] Verification call before treating number as production-active
- [ ] On partial failure: number is **not** auto-released; recover via `provisioning_state=partial`

## Agent / resolve checks

- [ ] SIP unknown DID → session ends without greeting
- [ ] Inactive / unverified DID → reject
- [ ] Signed metadata conflicting with DID → reject
- [ ] Active DID → correct `tenant_id` on call logs
- [ ] Active DID → correct `agent_profile_id` (phone assignment or tenant default)
- [ ] Assigning a phone to a profile refreshes LiveKit dispatch `RoomAgentDispatch.metadata`
- [ ] `CallState.important_details` includes caller/called E.164 + SIP ids
- [ ] SIP uses `BVCTelephony`; browser uses `BVC`
- [ ] Concurrent calls (2–3) answer independently
- [ ] Ops `/phones` + `/agents` test-call issues signed metadata with `agent_profile_id`

## Exit criteria

- [ ] Inbound PSTN call talks to the same Realtime agent
- [ ] Correct `tenant_id` attached to the call session
- [ ] Correct Agent Profile (greeting / tools) for the assigned DID
