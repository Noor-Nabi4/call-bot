# Invoicing (Phase 18)

Customer invoices for the Business OS — authoritative totals, balances, and lifecycle.

**Status:** Application implementation complete; provider/staging verification pending.  
**Production gate:** `PRODUCTION BLOCKED` until Phase 19 payments + staging smoke.

## Architecture

```text
Invoice (DRAFT → SENT → PARTIALLY_PAID / PAID / OVERDUE / VOID)
  ├── Line items (SERVICE / PRODUCT / CUSTOM — server pricing)
  ├── InvoiceCalculationService (totals + balance_due)
  ├── InvoicePaymentApplication (ledger until Phase 19 payment_id)
  └── NotificationOutbox (email on send — delivery ≠ financial state)
```

**RAG vs tools:** Invoice totals, balance, and payment state are operational truth (tools/DB). RAG may only answer policy/terms copy.

## API

Prefix: `/api/admin/crm/invoices` (RBAC: `invoices.read|create|update|send|void`).

Migration: `0046_invoicing`.

## Verification

| Check | Status |
| ----- | ------ |
| Unit tests (`test_invoices_crm.py`) | VERIFIED |
| PG numbering concurrency | VERIFIED when PG available |
| Stripe Connect / payment provider | NOT EXECUTED (Phase 19) |
| Email provider live | NOT EXECUTED |
| Staging | NOT EXECUTED |
