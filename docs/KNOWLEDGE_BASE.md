# Knowledge Base / RAG (Phase 16)

Multi-tenant knowledge ingestion and retrieval shared by Voice, SMS, and ops.

**Status:** Implementation and local verification complete; provider/staging verification pending.  
**Production gate:** `PRODUCTION BLOCKED — APPLICATION COMPLETE / FROZEN` (provider + staging only).

```text
Implementation complete
Local verification complete
Provider verification pending
Staging verification pending
Production verification pending
```

---

## Architecture

```text
Source (PDF/DOCX/Website/Text/FAQ/Policy/…)
      ↓
KnowledgeSource + async job (knowledge.ingest)
      ↓
Extract → Normalize → Chunk → Embed
      ↓
knowledge_chunks (+ pgvector embedding_vec on PostgreSQL)
      ↓
KnowledgeRetrievalService
      ↓
Voice / SMS / AIToolExecutor.search_knowledge / Ops UI
```

### RAG vs tools (hard rule)

| RAG (informational) | Tools (authoritative) |
| ------------------- | --------------------- |
| FAQs, policies, warranties | Inventory, prices |
| Business information | Availability, appointments |
| Product descriptions (features) | Orders, payments, customers |
| Installation / return policy copy | Booking state |

Retrieved documents are **untrusted reference data**. Prompt-injection phrases are sanitized; models must not treat document text as instructions.

---

## Source types

`PDF` · `DOCX` · `WEBSITE` · `TEXT` · `FAQ` · `POLICY` · `BUSINESS_INFORMATION` · `PRODUCT_DESCRIPTION`

Statuses: `PROCESSING` → `ACTIVE` | `FAILED` · `ARCHIVED` · `DELETED`

---

## Ingestion

1. Create source (ops API) — store object in tenant-prefixed storage when uploading files  
2. Enqueue `knowledge.ingest` (idempotent per source+version)  
3. Extract / normalize / chunk / embed  
4. Activate version; prior ACTIVE version stays searchable if reindex fails  

**Chunking:** paragraph-aware; target 800 chars, max 1200, overlap 100 (character-based).

**Embeddings:** `EmbeddingService` — OpenAI `text-embedding-3-small` (1536-d) when `OPENAI_API_KEY` set; deterministic `FakeEmbeddingService` for local/tests only.

---

## Retrieval

`KnowledgeRetrievalService.retrieve(tenant_id, query, top_k=, filters=, relevance_threshold=, channel=)`

- Tenant filter at query layer (never global search then filter in memory as sole control)
- Metadata filters: `source_type`, `category`, `source_id`
- Default top-K 5; max context chars 6000; max 3 chunks/source
- Default relevance threshold **0.35** (cosine); tune with real OpenAI scores in staging
- Hybrid fallback to curated `KnowledgeArticle` keyword search when no vector hits

AI tool: `search_knowledge` (Phase 14 registry, group `knowledge`).  
SMS: `search_knowledge` in `SMS_ALLOWED_TOOLS`.  
Voice: `/internal/knowledge/search` now returns hybrid RAG results (compatible article shape).

---

## Security

- Tenant isolation on every source/chunk query  
- SSRF: block localhost, private/link-local IPs, metadata hosts; re-validate redirects  
- File validation: size, MIME, PDF/DOCX magic  
- Metadata allow-list + size bounds  
- RBAC: `knowledge.read` / `knowledge.manage` (reindex under manage)  
- Soft delete deactivates chunks; audit retained  

---

## APIs

```text
GET    /api/knowledge/sources
POST   /api/knowledge/sources/text
POST   /api/knowledge/sources/website
POST   /api/knowledge/sources/upload
GET    /api/knowledge/sources/{id}
GET    /api/knowledge/sources/{id}/status
POST   /api/knowledge/sources/{id}/reindex
DELETE /api/knowledge/sources/{id}
POST   /api/knowledge/semantic-search
```

Legacy curated articles at `/api/knowledge` remain.

---

## Ops

- Apply Alembic `0045_knowledge_rag` (requires PostgreSQL `vector` extension)
- Set `OPENAI_API_KEY`, optional `KNOWLEDGE_*` overrides
- Run async job worker for background ingest (or `sync=true` for small text in staging)

### Staging smoke

1. Create FAQ/policy text source with sync  
2. Semantic search returns chunks above threshold  
3. Cross-tenant isolation  
4. PDF upload + reindex  
5. Website URL (public only)  
6. Voice/SMS informational question grounded; inventory question still uses tools  

---

## Verification status

| Check | Status |
| ----- | ------ |
| Local RAG tests (`test_knowledge_rag.py`) | VERIFIED (12+) |
| Local PG + pgvector (`test_knowledge_rag_pg.py`) | VERIFIED when PG available |
| Curated KB regression (`test_knowledge.py`) | VERIFIED |
| Phase 14 AI tools + Phase 15 SMS subset | VERIFIED (63 passed with RAG/SMS/AI suite) |
| Full platform pytest | VERIFIED (608 passed, 1 skipped) |
| Frontend lint / tsc / tests / build | VERIFIED (42 frontend tests; build OK) |
| Large-scale perf (1k sources / 10k chunks) | NOT EXECUTED |
| OpenAI embeddings live | NOT EXECUTED |
| Real PDF/DOCX/website staging | NOT EXECUTED |
| Production | NOT EXECUTED |

**Gate:** `PRODUCTION BLOCKED` — application frozen; remaining work is provider + staging + production smoke.

PG vector search runs inside a savepoint so a missing `embedding_vec` / extension cannot abort SMS or AI tool transactions (falls back to JSON embedding cosine).
