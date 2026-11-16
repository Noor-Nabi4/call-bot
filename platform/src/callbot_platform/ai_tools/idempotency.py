"""AI tool operation_id replay using existing TelephonyIdempotencyKey table.

Semantics:
  - Key is scoped by (tenant_id, operation=ai_tool:{tool}, key=operation_id)
  - Same operation_id + same args fingerprint → return stored result
  - Same operation_id + different args → idempotency_conflict
  - operation_id is tenant-scoped, not call-scoped: Call B reusing Call A's
    operation_id returns the prior result (no duplicate mutation)
  - On PostgreSQL, concurrent same-tenant/tool/operation_id callers are
    serialized with a transaction-scoped advisory lock before lookup/mutate
"""

from __future__ import annotations

import hashlib
import logging
from typing import Any
from uuid import UUID

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from callbot_platform.ai_tools.confirmation import args_fingerprint
from callbot_platform.db.models.tenant import TelephonyIdempotencyKey

logger = logging.getLogger(__name__)


def _operation(tool_name: str) -> str:
    return f"ai_tool:{tool_name}"[:64]


def acquire_xact_lock(
    session: Session,
    *,
    tenant_id: UUID,
    tool_name: str,
    operation_id: UUID,
) -> None:
    """Serialize concurrent executions of the same tenant+tool+operation_id.

    Uses pg_advisory_xact_lock (released at transaction end). No-op on
    non-PostgreSQL dialects (SQLite unit tests).
    """
    bind = session.get_bind()
    if bind is None or bind.dialect.name != "postgresql":
        return
    material = f"{tenant_id}:ai_tool:{tool_name}:{operation_id}".encode()
    # Two int4 keys from sha256 to reduce advisory-lock collision risk.
    digest = hashlib.sha256(material).digest()
    k1 = int.from_bytes(digest[:4], "big", signed=True)
    k2 = int.from_bytes(digest[4:8], "big", signed=True)
    try:
        session.execute(
            text("SELECT pg_advisory_xact_lock(:k1, :k2)"),
            {"k1": k1, "k2": k2},
        )
    except Exception:
        logger.warning(
            "ai_idempotency_advisory_lock_failed tool=%s", tool_name, exc_info=True
        )


def lookup(
    session: Session,
    *,
    tenant_id: UUID,
    tool_name: str,
    operation_id: UUID,
    args: dict[str, Any],
) -> tuple[str, dict[str, Any] | None]:
    """Return ('miss', None), ('hit', result), or ('conflict', None)."""
    row = session.scalar(
        select(TelephonyIdempotencyKey).where(
            TelephonyIdempotencyKey.tenant_id == tenant_id,
            TelephonyIdempotencyKey.operation == _operation(tool_name),
            TelephonyIdempotencyKey.key == str(operation_id),
        )
    )
    if row is None:
        return "miss", None
    stored = row.response_json or {}
    prior_fp = stored.get("args_fp")
    current_fp = args_fingerprint(args)
    if prior_fp and prior_fp != current_fp:
        return "conflict", None
    result = stored.get("result")
    if isinstance(result, dict):
        return "hit", result
    return "miss", None


def store(
    session: Session,
    *,
    tenant_id: UUID,
    tool_name: str,
    operation_id: UUID,
    args: dict[str, Any],
    result: dict[str, Any],
) -> None:
    existing = session.scalar(
        select(TelephonyIdempotencyKey).where(
            TelephonyIdempotencyKey.tenant_id == tenant_id,
            TelephonyIdempotencyKey.operation == _operation(tool_name),
            TelephonyIdempotencyKey.key == str(operation_id),
        )
    )
    payload = {
        "args_fp": args_fingerprint(args),
        "result": result,
    }
    if existing is not None:
        existing.response_json = payload
        existing.status = "completed"
        return
    session.add(
        TelephonyIdempotencyKey(
            tenant_id=tenant_id,
            operation=_operation(tool_name),
            key=str(operation_id),
            response_json=payload,
            status="completed",
        )
    )
