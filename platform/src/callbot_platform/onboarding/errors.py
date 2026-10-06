"""Onboarding domain errors."""

from __future__ import annotations


class OnboardingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
