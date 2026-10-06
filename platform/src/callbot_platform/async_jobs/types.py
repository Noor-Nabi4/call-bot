"""Async job status and type constants."""

from __future__ import annotations


class JobStatus:
    PENDING = "pending"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    RETRY_WAIT = "retry_wait"
    FAILED = "failed"
    DEAD_LETTER = "dead_letter"
    CANCELLED = "cancelled"


class JobType:
    TELEPHONY_PROVISION_PURCHASE = "telephony.provision_purchase"
    TELEPHONY_PROVISION_CONNECT = "telephony.provision_connect"
    TELEPHONY_RELEASE = "telephony.release"
    TELEPHONY_REFRESH_DISPATCH = "telephony.refresh_dispatch"
    STRIPE_SIGNUP_PROVISION = "stripe.signup_provision"
    STRIPE_CHECKOUT_PROVISION = "stripe.checkout_provision"
