# Call Intelligence (Phase 23)

Enrichment layer on top of existing Calls / Voice Agent. Does **not** replace CRM domains or the Phase 22 Automation Engine.

## Architecture

```text
CALL
  → Recording reference (recording_objects + private object storage)
  → Async job call.transcribe
  → call_transcripts + call_transcript_segments
  → Automation event CALL_TRANSCRIBED
  → Async job call.analyze
  → call_intelligence (structured summary + classification)
  → Automation events CALL_ANALYZED / CALL_CLASSIFIED
  → Existing Phase 22 Automation Engine
```

Authoritative CRM state (appointments, jobs, payments, …) always comes from domain services. Transcript claims never create appointments or mutate invoices.

## Recording lifecycle

Statuses: `PENDING` → `AVAILABLE` / `PROCESSING` → `READY` → `EXPIRED` / `FAILED` / `DELETED`.

Lifecycle: `ACTIVE` → `EXPIRED` → `DELETED` (cleanup worker deletes storage objects idempotently).

Storage keys (server-authored only):

```text
tenants/{tenant_id}/calls/{call_id}/recordings/{recording_id}/audio
```

Access: RBAC `calls.recordings.read` → short-lived signed URL. Never log signed URLs.

## Transcript lifecycle

`PENDING` → `PROCESSING` → `COMPLETED` | `FAILED` (bounded retries via async jobs).

Speakers: `CUSTOMER` | `AGENT` | `SYSTEM` | `UNKNOWN` (mapped from provider metadata; never inferred solely from text).

Segments preserve provider timestamps (`start_ms` / `end_ms` / `sequence`).

Search: tenant-scoped PostgreSQL FTS (`search_vector`) with ILIKE fallback.

## AI analysis lifecycle

Model output is structured intelligence only (no tools, no DB writes).

Fields: intent, problem, outcome, sentiment, appointment_status, follow_up, important_notes, classification.

- Controlled enums for intent / classification / sentiment / follow-up.
- `appointment_status` prefers Appointment domain when a linked appointment exists.
- Operational signals (human transfer, spam disposition, booking/cancel tools) override AI classification (`RULE` / `HYBRID`).
- Transcript text is untrusted; prompt boundaries prevent instruction-following from caller content.
- Re-analysis creates a new `analysis_version` (history is not silently overwritten).

## Classification taxonomy

`BOOKING`, `RESCHEDULING`, `CANCELLATION`, `SALES`, `SUPPORT`, `EMERGENCY`, `BILLING`, `PRODUCT_INQUIRY`, `ORDER_INQUIRY`, `SPAM`, `HUMAN_TRANSFER`, `OTHER`.

Confidence is informational (`0..1`); it does not authorize actions.

## Retention

Per-tenant (`tenant_retention_settings`):

| Setting | Purpose |
| --- | --- |
| `recording_enabled` | Allow recording ingest |
| `transcription_enabled` | Allow transcription jobs |
| `recording_retention_days` | Recording expiry |
| `transcript_retention_days` | Transcript expiry |
| `analysis_retention_days` | Analysis expiry |

Recording / transcript / analysis retention are independent. Cleanup job: `call.intelligence_retention`.

## Providers

| Env | Default | Notes |
| --- | --- | --- |
| `CALL_TRANSCRIPTION_PROVIDER` | `deterministic` | Offline/test adapter; wire live STT when configured |
| `CALL_ANALYSIS_PROVIDER` | `deterministic` | Rules adapter; `openai` when `OPENAI_API_KEY` set |
| `CALL_INTELLIGENCE_MODEL` | `gpt-4o-mini` | Used when analysis provider is `openai` |
| `OBJECT_STORAGE_*` | existing | Private objects + signed URLs |

Live Twilio/LiveKit recording egress and live STT verification: **pending** until credentials/fleet available.

## RBAC

| Permission | Use |
| --- | --- |
| `calls.recordings.read` | View / presign recording |
| `calls.recordings.manage` | Manage recordings / retention |
| `calls.transcripts.read` | Transcript + search |
| `calls.intelligence.read` | Summary / classification |
| `calls.intelligence.manage` | Reanalyze |

Not granted to all CRM roles by default (CSR gets transcript/intelligence read; recordings require manager/owner).

## API

```text
GET  /api/admin/crm/calls/{id}/recording
GET  /api/admin/crm/calls/{id}/transcript
GET  /api/admin/crm/calls/{id}/intelligence
GET  /api/admin/crm/calls/{id}/classification
POST /api/admin/crm/calls/{id}/reanalyze
GET  /api/admin/crm/call-intelligence
GET  /api/admin/crm/call-intelligence/search
```

## Workers

| Job type | Behavior |
| --- | --- |
| `call.transcribe` | Idempotent by recording; emits `CALL_TRANSCRIBED`; enqueues analyze |
| `call.analyze` | Idempotent by input hash; emits `CALL_ANALYZED` + `CALL_CLASSIFIED` |
| `call.intelligence_retention` | Expire then delete recordings/transcripts/analysis |

Permanent provider/domain errors return `permanent: true` (no infinite retry).

## Phase 22 integration

New automation event types: `CALL_TRANSCRIBED`, `CALL_ANALYZED`, `CALL_CLASSIFIED`.

Condition fields: `call.classification`, `call.sentiment`, `call.intent`.

## Privacy / security

- Tenant scope on every query and signed URL.
- IDOR: cross-tenant UUID access returns not-found.
- No storage credentials or signed URLs in logs.
- Avoid logging full transcripts; log call/recording IDs.
- AI never receives internal tenant control plane instructions as executable commands from transcript content.

## Production verification

Required before production: migrate `0051_call_intelligence`, configure object storage, configure live transcription/analysis providers, run retention worker, staging RBAC/IDOR drills, live recording webhook idempotency.
