"""Domain enums for telephony provisioning."""

from __future__ import annotations

from enum import Enum


class TenantStatus(str, Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"


class TelephonyProviderId(str, Enum):
    TWILIO = "twilio"


class OnboardingPath(str, Enum):
    CONNECT_EXISTING = "connect_existing"
    PLATFORM_PURCHASE = "platform_purchase"


class AuthMethod(str, Enum):
    MANUAL = "manual"
    PLATFORM_SUBACCOUNT = "platform_subaccount"
    OAUTH = "oauth"  # reserved for future Twilio OAuth


class ConnectionStatus(str, Enum):
    PENDING_SETUP = "pending_setup"
    CONFIGURING = "configuring"
    PENDING_VERIFICATION = "pending_verification"
    ACTIVE = "active"
    FAILED = "failed"
    RELEASED = "released"
    PARTIAL = "partial"


class VerificationStatus(str, Enum):
    UNVERIFIED = "unverified"
    PENDING = "pending"
    VERIFIED = "verified"
    FAILED = "failed"


class ProvisioningState(str, Enum):
    NONE = "none"
    IN_PROGRESS = "in_progress"
    PARTIAL = "partial"
    COMPLETE = "complete"
    FAILED = "failed"
