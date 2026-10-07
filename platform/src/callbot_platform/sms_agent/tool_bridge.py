"""Thin bridge from SMS agent to Phase 14 AIToolExecutor — no domain duplication."""

from __future__ import annotations

import logging
import uuid
from typing import Any
from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.ai_tools import AIToolExecutor
from callbot_platform.ai_tools.policy import customer_safe_message
from callbot_platform.sms_agent.constants import SMS_ALLOWED_TOOLS

logger = logging.getLogger(__name__)


class SmsToolBridge:
    def __init__(
        self,
        session: Session,
        *,
        hmac_secret: str | None = None,
    ) -> None:
        self._executor = AIToolExecutor(session, hmac_secret=hmac_secret)

    def invoke(
        self,
        tool_name: str,
        *,
        tenant_id: UUID,
        args: dict[str, Any] | None = None,
        customer_id: UUID | None = None,
        caller_phone: str | None = None,
        operation_id: UUID | None = None,
        confirmed: bool = False,
        confirmation_token: str | None = None,
    ) -> dict[str, Any]:
        if tool_name not in SMS_ALLOWED_TOOLS:
            logger.warning("sms_tool_not_allowed tool=%s", tool_name)
            return {
                "ok": False,
                "error": {
                    "code": "permission_denied",
                    "retryable": False,
                    "customerSafe": True,
                },
            }
        op = operation_id or uuid.uuid4()
        result = self._executor.execute(
            tool_name,
            tenant_id=tenant_id,
            call_id=None,
            args=args or {},
            operation_id=op,
            customer_id=customer_id,
            caller_phone=caller_phone,
            confirmed=confirmed,
            confirmation_token=confirmation_token,
        )
        logger.info(
            "sms.tool.executed tool=%s tenant_id=%s operation_id=%s ok=%s",
            tool_name,
            tenant_id,
            op,
            result.get("ok"),
        )
        return result

    @staticmethod
    def customer_safe(result: dict[str, Any]) -> str:
        if result.get("ok"):
            return ""
        err = result.get("error") or {}
        code = str(err.get("code") or "system_unavailable")
        return customer_safe_message(code)
