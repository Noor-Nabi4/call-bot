"""Structured errors for AI business setup."""

from __future__ import annotations


class AiBusinessSetupError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
