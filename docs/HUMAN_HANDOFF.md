# Human Handoff (Phase 24)

Connects AI Voice / SMS to human agents with a frozen context snapshot — never a blind transfer.

## Architecture

```text
AI tool request_human / manual create
  → HandoffContextService (immutable snapshot)
  → HandoffRoutingService (emergency / dept / tech / hours / default)
  → handoff_requests + handoff_assignments + handoff_history
  → Phase 22 events (HANDOFF_*)
  → NotificationService (SMS to escalation) + TelephonyTransferProvider
  → CRM UI /crm/handoffs
```

Reuses: Call Intelligence, BusinessHours/holidays, NotificationOutbox, Automations, existing `TenantHandoffSettings` (enable + escalation phone + SIP trunk), CallQueueItem (legacy supervisor queue sync).

## Tables

- `departments` — Sales, Support, Dispatch, Billing, Emergency
- `handoff_requests` — channel, status, priority, context_snapshot JSON
- `handoff_assignments` — USER / DEPARTMENT / TECHNICIAN / QUEUE
- `handoff_history` — CREATED → ROUTED → ASSIGNED → CONNECTED → COMPLETED

Migration: `0052_human_handoff`.

## Context snapshot

Stored at creation (not recalculated on view):

customer, intent, summary, transcript, sentiment, classification, jobs, appointments, ai_actions, recording metadata, emergency, business_hours, transfer_reason.

Signed `recording_url` is issued on authorized GET only.

## Routing

1. Emergency → emergency department / queue, priority EMERGENCY  
2. Technician target → TECHNICIAN assignment  
3. User target → USER assignment  
4. Department → DEPARTMENT queue  
5. After hours / holiday → after_hours queue  
6. Else → default queue  

Emergency signals: explicit flag, classification `EMERGENCY` (confidence ≥ 0.75), or keyword match.

## AI tool

`request_human({ reason, summary, department?, emergency? })`  
`confirmation_required=false`. AI cannot select tenant/user/permissions; executor routes.

## Automation events

`HANDOFF_CREATED`, `HANDOFF_ASSIGNED`, `HANDOFF_CONNECTED`, `HANDOFF_COMPLETED`  
Condition fields: `handoff.priority`, `handoff.channel`, `handoff.status`.

## RBAC

`handoffs.read`, `handoffs.manage`, `handoffs.accept`  
(Existing `handoff.read` / `handoff.manage` remain for legacy settings UI.)

## APIs

```text
GET/POST /api/admin/crm/handoffs
GET      /api/admin/crm/handoffs/{id}
POST     /api/admin/crm/handoffs/{id}/accept|reject|complete
GET/PUT  /api/admin/crm/departments
```

## Telephony

`TelephonyTransferProvider.transfer_call()` — domain has no Twilio/LiveKit SDK calls.  
Default `NoOpTransferProvider` records intent; Twilio/LiveKit provider classes are stubs.  
Voice-agent may execute LiveKit SIP transfer when configured — **live PSTN/SIP path is NOT VERIFIED**.

Intended production path:

```text
Customer → Twilio → LiveKit → AI Voice Agent → request_human
  → HumanHandoffService (snapshot + route) → LiveKit/Twilio transfer → Human
```

Human must already have customer, intent, summary, transcript, recording, jobs,
appointments, AI actions, and emergency/priority before speaking.

## Status

```text
APPLICATION COMPLETE / FROZEN
PRODUCTION BLOCKED
```

Primary blockers: live voice transfer + PostgreSQL assignment race verification.

## Out of scope (do not add to close Phase 24)

Slack/Teams UI, WebRTC contact center, skills-based routing, presence,
agent desktop, multi-agent ACD.
