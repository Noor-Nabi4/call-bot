"""Human Handoff domain errors."""

from __future__ import annotations


class HandoffDomainError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
