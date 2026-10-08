"""Structured errors for agent configuration."""

from __future__ import annotations


class AgentConfigError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
