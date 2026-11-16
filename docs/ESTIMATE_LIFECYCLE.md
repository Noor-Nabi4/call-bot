# Estimate Lifecycle

```text
DRAFT → SENT → VIEWED → APPROVED → CONVERTED
                 ↘ REJECTED
                 ↘ EXPIRED
                 ↘ CANCELLED
DRAFT → CANCELLED
APPROVED → EXPIRED | CANCELLED
```

Status changes only via explicit endpoints (`/send`, `/view`, `/approve`, `/reject`, `/cancel`, `/convert`). Arbitrary `PATCH status` is rejected.

## Expiration

`valid_until` is evaluated server-side (UTC-aware). Expired estimates cannot be approved or converted (`estimate_expired`).

## History

Every transition appends `estimate_status_history` with actor, reason, and timestamps. History is never overwritten.
