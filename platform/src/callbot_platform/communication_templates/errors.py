"""Domain errors for communication templates."""

from __future__ import annotations

from callbot_platform.crm.errors import CrmError


class CommunicationTemplateError(CrmError):
    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(code, message)
        self.retryable = retryable
