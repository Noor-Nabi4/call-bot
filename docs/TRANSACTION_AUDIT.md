# Transaction Audit

**Date:** 2026-10-06  
**Scope:** External I/O that runs while a SQLAlchemy session from `get_db()` is still open (committed only after the request returns).

## Transaction model

`callbot_platform.db.get_db()` opens an implicit transaction, yields the session, **commits on success**, rolls back on exception. There are no `after_commit` hooks. Any HTTP/Twilio/LiveKit/Stripe call during a request therefore holds a DB connection and risks dual-write bugs.

---

## Findings

| File | Function | TX boundary | External operation | Risk | Recommended fix | Phase 2 status |
|------|----------|-------------|--------------------|------|-----------------|----------------|
| `scheduling/notifications.py` | `_enqueue_and_maybe_send_sms` | flush outbox inside `get_db` | Twilio SMS | **critical** | Enqueue pending only; worker after commit | **Fixed** |
| `scheduling/repos/appointment_repo.py` | `book` / `reschedule` / `cancel` | same TX | SMS via NotificationService | **critical** | Same as above | **Fixed** |
| `automation/service.py` | `_run_action` `post_webhook` | same TX as caller | `httpx` webhook | **high** | Enqueue webhook outbox; worker delivers | **Fixed** |
| `api/crm_routes.py` | `call_end` | `get_db` | automation webhooks | **high** | Webhook outbox | **Fixed** |
| `telephony/services/purchase.py` | `purchase` / `ensure_subaccount` / `release` | `get_db` | Twilio + LiveKit | **critical** | Saga / intent then provision (documented; deferred) | Deferred |
| `telephony/services/connect_existing.py` | `start` | `get_db` | LiveKit trunk/dispatch | **high** | After-commit provision (deferred) | Deferred |
| `telephony/services/phone_assign.py` | `assign_profile` | `get_db` | LiveKit metadata update | **high** | After-commit refresh (deferred) | Deferred |
| `billing/service.py` | `signup` / checkout | flush then Stripe | Stripe Customer/Checkout | **high** | Commit then Stripe (deferred) | Deferred |
| `billing/service.py` | `create_portal_session` | read TX | Stripe portal | **low** | Short read then Stripe | Acceptable |
| `scheduling/notifications.py` | email branch | flush pending row | none | safe | Worker drains email | **Worker ready** |

---

## Fixed in Phase 2

1. SMS: insert `notification_outbox` with `status=pending` only; no Twilio call in the request TX.
2. Automation webhooks: insert outbox row `channel=webhook` with payload; no `httpx` in the request TX.
3. Worker claims with `FOR UPDATE SKIP LOCKED` (Postgres), commits claim, performs I/O, then updates result.

## Explicitly deferred

Telephony purchase/connect and Stripe signup still perform provider I/O inside request transactions. They need a dedicated provisioning saga (multi-step status machine). Tracked as next phase; do not confuse with notification outbox work.

---

## Anti-pattern (forbidden going forward)

```text
BEGIN
  DB write
  Twilio / SMS / email / webhook / LiveKit HTTP
COMMIT
```

## Required pattern

```text
BEGIN
  business row + outbox row (pending)
COMMIT
→ worker claim → COMMIT claim
→ external I/O
→ UPDATE outbox success/retry/dead_letter
```
