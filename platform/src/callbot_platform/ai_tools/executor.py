"""Common AI tool execution pipeline with timeouts, confirmation tokens, idempotency."""

from __future__ import annotations

import logging
import time
from typing import Any
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from sqlalchemy.orm import Session

from callbot_platform.ai_tools import idempotency as idem
from callbot_platform.ai_tools.confirmation import (
    issue_confirmation_token,
    verify_confirmation_status,
)
from callbot_platform.ai_tools.errors import map_exception
from callbot_platform.ai_tools.handlers import (
    AIToolHandlers,
    load_call_customer_id,
    load_caller_phone,
)
from callbot_platform.ai_tools.policy import TIMEOUT_SECONDS
from callbot_platform.ai_tools.registry import TOOL_SPECS, ToolSpec, get_tool_spec
from callbot_platform.ai_tools.types import (
    ACTOR_AI_SMS,
    ACTOR_AI_VOICE,
    FORBIDDEN_ARG_KEYS,
    STATUS_FILTER_ALLOWED,
    AIToolContext,
    AIToolResult,
    ok_result,
    tool_error,
)
from callbot_platform.config import get_settings
from callbot_platform.rbac.errors import RbacError
from callbot_platform.rbac.service import AuthorizationService
from callbot_platform.telephony.audit import write_audit

logger = logging.getLogger(__name__)


class AIToolExecutor:
    def __init__(
        self,
        session: Session,
        *,
        hmac_secret: str | None = None,
    ) -> None:
        self._session = session
        self._auth = AuthorizationService(session)
        self._handlers = AIToolHandlers(session)
        settings = get_settings()
        self._hmac_secret = (
            hmac_secret
            if hmac_secret is not None
            else (settings.metadata_hmac_secret or "")
        )

    def execute(
        self,
        tool_name: str,
        *,
        tenant_id: UUID,
        call_id: UUID | None,
        args: dict[str, Any] | None,
        operation_id: UUID | None = None,
        customer_id: UUID | None = None,
        caller_phone: str | None = None,
        confirmed: bool = False,
        confirmation_token: str | None = None,
        conversation_id: UUID | None = None,
    ) -> dict[str, Any]:
        started = time.perf_counter()
        spec = get_tool_spec(tool_name)
        if spec is None:
            return self._finish(
                tool_error("not_found").to_dict(),
                tool_name=tool_name,
                tenant_id=tenant_id,
                call_id=call_id,
                operation_id=operation_id,
                started=started,
            )

        raw_args = dict(args or {})
        forbidden = self._forbidden_keys(tool_name, raw_args)
        if forbidden:
            logger.warning(
                "ai_tool_forbidden_args tool=%s keys=%s",
                tool_name,
                sorted(forbidden),
            )
            return self._finish(
                tool_error("invalid_arguments").to_dict(),
                tool_name=tool_name,
                tenant_id=tenant_id,
                call_id=call_id,
                operation_id=operation_id,
                started=started,
            )

        try:
            parsed = spec.args_model.model_validate(raw_args)
            # Canonical dump for fingerprint / confirmation (aliases as wire names).
            wire_args = parsed.model_dump(by_alias=True, exclude_none=True)
        except ValidationError:
            return self._finish(
                tool_error("invalid_arguments").to_dict(),
                tool_name=tool_name,
                tenant_id=tenant_id,
                call_id=call_id,
                operation_id=operation_id,
                started=started,
            )

        if spec.idempotency_required and operation_id is None:
            return self._finish(
                tool_error("invalid_arguments").to_dict(),
                tool_name=tool_name,
                tenant_id=tenant_id,
                call_id=call_id,
                operation_id=operation_id,
                started=started,
            )

        # Phase 30: capability gate before confirmation / RBAC / mutation.
        try:
            from callbot_platform.agent_config.enforcement import (
                assert_tool_capability,
            )
            from callbot_platform.agent_config.errors import AgentConfigError

            assert_tool_capability(self._session, tenant_id, tool_name)
        except AgentConfigError as exc:
            code = (
                "capability_disabled"
                if exc.code == "CAPABILITY_DISABLED"
                else "system_unavailable"
            )
            return self._finish(
                tool_error(code).to_dict(),
                tool_name=tool_name,
                tenant_id=tenant_id,
                call_id=call_id,
                operation_id=operation_id,
                started=started,
            )

        if spec.confirmation_required:
            if operation_id is None:
                return self._finish(
                    tool_error("invalid_arguments").to_dict(),
                    tool_name=tool_name,
                    tenant_id=tenant_id,
                    call_id=call_id,
                    operation_id=operation_id,
                    started=started,
                )
            if not self._hmac_secret.strip():
                logger.error("ai_confirmation_secret_missing tool=%s", tool_name)
                return self._finish(
                    tool_error("system_unavailable").to_dict(),
                    tool_name=tool_name,
                    tenant_id=tenant_id,
                    call_id=call_id,
                    operation_id=operation_id,
                    started=started,
                )
            if not confirmed:
                token = issue_confirmation_token(
                    secret=self._hmac_secret,
                    tenant_id=tenant_id,
                    call_id=call_id,
                    tool_name=tool_name,
                    operation_id=operation_id,
                    args=wire_args,
                )
                out = tool_error("confirmation_required").to_dict()
                out["confirmationToken"] = token
                return self._finish(
                    out,
                    tool_name=tool_name,
                    tenant_id=tenant_id,
                    call_id=call_id,
                    operation_id=operation_id,
                    started=started,
                )
            conf_status = verify_confirmation_status(
                secret=self._hmac_secret,
                token=confirmation_token,
                tenant_id=tenant_id,
                call_id=call_id,
                tool_name=tool_name,
                operation_id=operation_id,
                args=wire_args,
            )
            if conf_status != "ok":
                code = (
                    "expired" if conf_status == "expired" else "confirmation_required"
                )
                return self._finish(
                    tool_error(code).to_dict(),
                    tool_name=tool_name,
                    tenant_id=tenant_id,
                    call_id=call_id,
                    operation_id=operation_id,
                    started=started,
                )

        if spec.idempotency_required and operation_id is not None:
            # Serialize same tenant+tool+operation_id before lookup/mutate so
            # concurrent replays cannot both miss and double-apply.
            idem.acquire_xact_lock(
                self._session,
                tenant_id=tenant_id,
                tool_name=tool_name,
                operation_id=operation_id,
            )
            status, prior = idem.lookup(
                self._session,
                tenant_id=tenant_id,
                tool_name=tool_name,
                operation_id=operation_id,
                args=wire_args,
            )
            if status == "conflict":
                return self._finish(
                    tool_error("idempotency_conflict").to_dict(),
                    tool_name=tool_name,
                    tenant_id=tenant_id,
                    call_id=call_id,
                    operation_id=operation_id,
                    started=started,
                )
            if status == "hit" and prior is not None:
                return self._finish(
                    prior,
                    tool_name=tool_name,
                    tenant_id=tenant_id,
                    call_id=call_id,
                    operation_id=operation_id,
                    started=started,
                    replay=True,
                )

        resolved_customer = customer_id or load_call_customer_id(self._session, call_id)
        resolved_phone = caller_phone or load_caller_phone(self._session, call_id)
        actor = ACTOR_AI_VOICE if call_id is not None else ACTOR_AI_SMS
        ctx = AIToolContext(
            tenant_id=tenant_id,
            call_id=call_id,
            actor_type=actor,
            operation_id=operation_id,
            customer_id=resolved_customer,
            caller_phone=resolved_phone,
            confirmed=confirmed,
            conversation_id=conversation_id,
        )

        try:
            self._auth.check_ai_tool(tenant_id, spec.tool_group)
            for perm in spec.permissions:
                self._auth.require_ai_permission(tenant_id, perm)
        except RbacError:
            return self._finish(
                tool_error("permission_denied").to_dict(),
                tool_name=tool_name,
                tenant_id=tenant_id,
                call_id=call_id,
                operation_id=operation_id,
                started=started,
            )

        budget = TIMEOUT_SECONDS.get(spec.timeout_class, 4.0)
        self._apply_statement_timeout(budget)

        try:
            result = self._handlers.dispatch(spec, ctx, parsed)
            if isinstance(result, AIToolResult):
                structured = result
            else:
                structured = ok_result(result)
        except (OperationalError, DBAPIError) as exc:
            msg = str(exc).lower()
            if "statement timeout" in msg or "canceling statement" in msg:
                structured = tool_error("system_unavailable")
            else:
                logger.exception(
                    "ai_tool_db_failed tool=%s tenant_id=%s", tool_name, tenant_id
                )
                structured = map_exception(exc)
        except Exception as exc:
            logger.exception(
                "ai_tool_failed tool=%s tenant_id=%s",
                tool_name,
                tenant_id,
            )
            structured = map_exception(exc)

        if not structured.ok:
            try:
                self._session.rollback()
            except Exception:
                logger.exception("ai_tool_rollback_failed tool=%s", tool_name)

        out = structured.to_dict()
        if structured.ok and spec.idempotency_required and operation_id is not None:
            try:
                idem.store(
                    self._session,
                    tenant_id=tenant_id,
                    tool_name=tool_name,
                    operation_id=operation_id,
                    args=wire_args,
                    result=out,
                )
            except Exception:
                logger.exception("ai_tool_idempotency_store_failed tool=%s", tool_name)

        return self._finish(
            out,
            tool_name=tool_name,
            tenant_id=tenant_id,
            call_id=call_id,
            operation_id=operation_id,
            started=started,
            mutation=spec.mutation,
        )

    def _apply_statement_timeout(self, seconds: float) -> None:
        bind = self._session.get_bind()
        if bind is None or bind.dialect.name != "postgresql":
            return
        ms = max(500, int(seconds * 1000))
        try:
            self._session.execute(text(f"SET LOCAL statement_timeout = {ms}"))
        except Exception:
            logger.warning("ai_tool_statement_timeout_set_failed", exc_info=True)

    def _finish(
        self,
        result: dict[str, Any],
        *,
        tool_name: str,
        tenant_id: UUID,
        call_id: UUID | None,
        operation_id: UUID | None,
        started: float,
        mutation: bool = False,
        replay: bool = False,
    ) -> dict[str, Any]:
        duration_ms = int((time.perf_counter() - started) * 1000)
        ok = bool(result.get("ok"))
        err = result.get("error") if isinstance(result.get("error"), dict) else {}
        error_code = err.get("code") if err else None
        logger.info(
            "ai_tool_executed tool=%s tenant_id=%s call_id=%s operation_id=%s "
            "ok=%s error_code=%s duration_ms=%s replay=%s",
            tool_name,
            tenant_id,
            call_id,
            operation_id,
            ok,
            error_code,
            duration_ms,
            replay,
        )
        try:
            write_audit(
                self._session,
                tenant_id=tenant_id,
                actor="AI_VOICE_AGENT",
                action=f"ai_tool.{tool_name}",
                resource_ids={
                    "call_id": str(call_id) if call_id else None,
                    "operation_id": str(operation_id) if operation_id else None,
                    "ok": ok,
                    "error": error_code,
                    "duration_ms": duration_ms,
                    "replay": replay,
                },
                idempotency_key=(
                    f"ai_tool_audit:{tool_name}:{operation_id}"
                    if operation_id and not replay
                    else None
                ),
                payload_summary={"mutation": mutation},
            )
        except Exception:
            logger.exception("ai_tool_audit_failed tool=%s", tool_name)
        if not replay:
            try:
                from callbot_platform.billing.usage_ledger import ingest_tool_call

                ingest_tool_call(
                    self._session,
                    tenant_id=tenant_id,
                    tool_name=tool_name,
                    operation_id=operation_id,
                    call_id=call_id,
                    ok=ok,
                    error_code=error_code,
                )
            except Exception:
                logger.exception("usage_ledger_tool_ingest_failed tool=%s", tool_name)
        result = dict(result)
        result["meta"] = {
            "durationMs": duration_ms,
            "tool": tool_name,
            "replay": replay,
        }
        return result

    @staticmethod
    def _forbidden_keys(tool_name: str, args: dict[str, Any]) -> set[str]:
        # Phase 31: also reject authoritative-injection keys (catalog may expand).
        from callbot_platform.ai_guardrails.authoritative import (
            AUTHORITATIVE_INJECTION_KEYS,
        )

        blocked = FORBIDDEN_ARG_KEYS | AUTHORITATIVE_INJECTION_KEYS
        forbidden = set()
        for key in args:
            if key in blocked:
                if key == "status" and tool_name in STATUS_FILTER_ALLOWED:
                    continue
                forbidden.add(key)
        return forbidden

    def list_tools(self) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for _name, spec in sorted(TOOL_SPECS.items()):
            out.append(self._spec_public(spec))
        return out

    @staticmethod
    def _spec_public(spec: ToolSpec) -> dict[str, Any]:
        schema = spec.args_model.model_json_schema()
        return {
            "name": spec.name,
            "description": spec.description,
            "toolGroup": spec.tool_group,
            "permissions": list(spec.permissions),
            "mutation": spec.mutation,
            "confirmationRequired": spec.confirmation_required,
            "idempotencyRequired": spec.idempotency_required,
            "timeoutClass": spec.timeout_class.value,
            "timeoutSeconds": TIMEOUT_SECONDS.get(spec.timeout_class),
            "tenantScope": "call_scope",
            "audit": True,
            "argsSchema": schema,
        }
