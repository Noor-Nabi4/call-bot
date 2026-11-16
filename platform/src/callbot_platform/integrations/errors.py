"""Structured integration errors — never include secrets in messages."""

from __future__ import annotations


class IntegrationError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        *,
        retryable: bool = False,
        retry_after: float | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable
        self.retry_after = retry_after


class AuthExpiredError(IntegrationError):
    def __init__(self, message: str = "Authorization expired") -> None:
        super().__init__("AUTH_EXPIRED", message, retryable=False)


class AuthRevokedError(IntegrationError):
    def __init__(self, message: str = "Authorization revoked") -> None:
        super().__init__("AUTH_REVOKED", message, retryable=False)


class PermissionDeniedError(IntegrationError):
    def __init__(self, message: str = "Provider permission denied") -> None:
        super().__init__("PERMISSION_DENIED", message, retryable=False)


class RateLimitedError(IntegrationError):
    def __init__(
        self, message: str = "Rate limited", *, retry_after: float | None = None
    ) -> None:
        super().__init__(
            "RATE_LIMITED", message, retryable=True, retry_after=retry_after
        )


class ProviderUnavailableError(IntegrationError):
    def __init__(self, message: str = "Provider unavailable") -> None:
        super().__init__("PROVIDER_UNAVAILABLE", message, retryable=True)


class UnsupportedOperationError(IntegrationError):
    def __init__(self, message: str = "Unsupported operation") -> None:
        super().__init__("UNSUPPORTED_OPERATION", message, retryable=False)


class MappingConflictError(IntegrationError):
    def __init__(self, message: str = "Mapping conflict") -> None:
        super().__init__("MAPPING_CONFLICT", message, retryable=False)


class WebhookInvalidError(IntegrationError):
    def __init__(self, message: str = "Invalid webhook") -> None:
        super().__init__("WEBHOOK_INVALID", message, retryable=False)


class NotConfiguredError(IntegrationError):
    def __init__(self, message: str = "Provider credentials not configured") -> None:
        super().__init__("NOT_CONFIGURED", message, retryable=False)
