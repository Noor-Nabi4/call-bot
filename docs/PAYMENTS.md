# Payments (Phase 19)

Stripe Checkout for customer invoice payments, applied through Phase 18 `InvoicePaymentService`.

**Status:** Application implementation complete; Stripe test-mode / staging verification pending.  
**Production gate:** `PRODUCTION BLOCKED — APPLICATION COMPLETE / FROZEN`

## Architecture

```text
Invoice (balance_due)
  ↓
PaymentService.create_payment_link → Stripe Checkout Session
  ↓
Customer pays on Stripe-hosted page
  ↓
POST /webhooks/stripe/payments (signature verified)
  ↓
Payment → SUCCEEDED
  ↓
InvoicePaymentService.record_payment
  ↓
invoice_payment_applications → amount_paid / balance_due / status
```

SaaS subscription billing (`/billing/webhooks/stripe`) is separate. Invoice payments use metadata `purpose=invoice_payment`.

### Refund accounting (explicit product policy)

Refunds unwind applied money through `InvoicePaymentService.reverse_payment`. Do not invent alternate accounting without a deliberate product change.

```text
Refund (Stripe verified)
  ↓
amount_paid decreases
balance_due increases
  ↓
Invoice status recalculated
```

Example:

```text
Invoice total $1000, paid in full
$300 refund
→ amount_paid = $700
→ balance_due = $300
→ invoice status = PARTIALLY_PAID

Full refund of net paid amount
→ amount_paid = $0
→ balance_due = invoice total (less any remaining applications)
→ invoice status = SENT (or OVERDUE when due date has passed)
```

Payment status (`REFUNDED` / `PARTIALLY_REFUNDED`) is separate from invoice status. This policy can become more complex later (credit memos, write-offs, net vs gross reporting); keep changes explicit and documented here.

## Configuration

```text
STRIPE_SECRET_KEY
STRIPE_WEBHOOK_SECRET          # or STRIPE_INVOICE_WEBHOOK_SECRET
STRIPE_PUBLISHABLE_KEY         # optional frontend
STRIPE_INVOICE_CHECKOUT_SUCCESS_URL
STRIPE_INVOICE_CHECKOUT_CANCEL_URL
```

Webhook endpoint: `POST /webhooks/stripe/payments`  
Events: `checkout.session.completed`, `payment_intent.succeeded|payment_failed|canceled`, `charge.refunded`

Browser `/success` redirects are informational only — never mark paid from the frontend.

## AI tools

| Tool | Confirmation |
| ---- | ------------ |
| `create_payment_link` | required |
| `send_payment_link_sms` | required |
| `send_payment_link_email` | required |
| `get_payment_status` | read-only |

AI never collects card data. Destination phone/email resolved server-side from the customer record.

## Migration

`0047_payments` — `payments`, `payment_refunds`

## Verification

| Check | Status |
| ----- | ------ |
| Local payment unit tests (Stripe mocked) | VERIFIED |
| Full platform pytest (local) | VERIFIED with open flake (see below) — **not** claimed 100% clean |
| Stripe test-mode live Checkout | NOT EXECUTED |
| Live webhook signature | NOT EXECUTED |
| Staging | NOT EXECUTED |

### Open: flaky PostgreSQL suite failure

During Phase 19 regression, the full platform suite reported **614 passed / 1 skipped** plus **one flaky failure that passed on re-run**:

- Observed: `tests/test_sms_agent_pg.py::test_sms_perf_hot_paths` (SQLAlchemy error under load/contention)
- Also noted earlier in the same freeze window: intermittent PG race flake on customer create concurrency (`test_customer_creation_race_same_phone`) that passed on retry

**Do not treat the suite as 100% clean until the flake is classified.** Application freeze is still valid; before production, determine whether the failure is:

1. a genuine concurrency defect in product code,
2. a test synchronization / timing problem, or
3. environmental PostgreSQL contention under parallel local pytest.

This item does **not** block Phase 19 application freeze; it **does** block claiming a fully clean regression gate for production.
