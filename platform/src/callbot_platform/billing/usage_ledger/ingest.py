"""Map operational events → usage ledger entries (idempotent)."""

from __future__ import annotations

import logging
import math
from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from callbot_platform.billing.usage import seconds_to_billable_minutes
from callbot_platform.billing.usage_ledger.categories import (
    AccountingProvenance,
    BillingStatus,
    CostBasis,
    UsageType,
)
from callbot_platform.billing.usage_ledger.ledger import UsageLedgerService
from callbot_platform.billing.usage_ledger.pricing import catalog_from_settings
from callbot_platform.config import Settings, get_settings
from callbot_platform.db.models import Call, CallCogs, RecordingObject
from callbot_platform.db.models.sms import SmsMessage

logger = logging.getLogger(__name__)


def ingest_call_end(
    session: Session,
    call: Call,
    *,
    cogs: CallCogs | None = None,
    settings: Settings | None = None,
) -> list[str]:
    """Record voice, LLM tokens, AI request, optional transcription from a closed call."""
    ledger = UsageLedgerService(session, catalog=catalog_from_settings(settings))
    recorded: list[str] = []
    occurred = call.ended_at or datetime.now(UTC)
    call_id = str(call.id)
    seconds = int(call.billable_seconds or 0)
    minutes = seconds_to_billable_minutes(seconds)

    # Voice: application wall-clock duration (ACTUAL_INTERNAL), cost = CONFIGURED_RATE.
    _, created = ledger.record(
        tenant_id=call.tenant_id,
        usage_type=UsageType.VOICE_MINUTES,
        quantity=minutes,
        idempotency_key=f"voice:{call_id}",
        source_type="call",
        source_id=call_id,
        occurred_at=occurred,
        provider="platform",
        provider_reference=call.room_name,
        usage_provenance=AccountingProvenance.ACTUAL_INTERNAL,
        cost_provenance=AccountingProvenance.CONFIGURED_RATE,
        billing_status=BillingStatus.UNBILLED,
        metadata={
            "billable_seconds": seconds,
            "rounding": "ceil_seconds_then_ceil_minutes",
        },
    )
    if created:
        recorded.append(UsageType.VOICE_MINUTES.value)

    _, created = ledger.record(
        tenant_id=call.tenant_id,
        usage_type=UsageType.AI_REQUESTS,
        quantity=1,
        idempotency_key=f"ai_request:call:{call_id}",
        source_type="call",
        source_id=call_id,
        occurred_at=occurred,
        provider="openai",
        usage_provenance=AccountingProvenance.ACTUAL_INTERNAL,
        cost_provenance=AccountingProvenance.UNAVAILABLE,
        cost_basis_override=CostBasis.NONE,
        billing_status=BillingStatus.UNBILLED,
    )
    if created:
        recorded.append(UsageType.AI_REQUESTS.value)

    usage: dict[str, Any] = {}
    if cogs is not None and isinstance(cogs.openai_usage, dict):
        usage = cogs.openai_usage
    else:
        metrics = call.metrics if isinstance(call.metrics, dict) else {}
        raw = metrics.get("openai_usage")
        if isinstance(raw, dict):
            usage = raw

    input_tokens = _token_sum(
        usage,
        (
            "input_tokens",
            "input_audio_tokens",
            "input_text_tokens",
            "input_cached_tokens",
        ),
    )
    output_tokens = _token_sum(
        usage,
        ("output_tokens", "output_audio_tokens", "output_text_tokens"),
    )
    # Only record LLM usage when provider/runtime payload is present — never invent.
    if input_tokens > 0:
        _, created = ledger.record(
            tenant_id=call.tenant_id,
            usage_type=UsageType.LLM_INPUT_TOKENS,
            quantity=input_tokens,
            idempotency_key=f"llm_in:call:{call_id}",
            source_type="call",
            source_id=call_id,
            occurred_at=occurred,
            provider="openai",
            usage_provenance=AccountingProvenance.ACTUAL_PROVIDER,
            cost_provenance=AccountingProvenance.CONFIGURED_RATE,
            billing_status=BillingStatus.UNBILLED,
            metadata={"openai_usage_keys": sorted(usage.keys())},
        )
        if created:
            recorded.append(UsageType.LLM_INPUT_TOKENS.value)
    if output_tokens > 0:
        _, created = ledger.record(
            tenant_id=call.tenant_id,
            usage_type=UsageType.LLM_OUTPUT_TOKENS,
            quantity=output_tokens,
            idempotency_key=f"llm_out:call:{call_id}",
            source_type="call",
            source_id=call_id,
            occurred_at=occurred,
            provider="openai",
            usage_provenance=AccountingProvenance.ACTUAL_PROVIDER,
            cost_provenance=AccountingProvenance.CONFIGURED_RATE,
            billing_status=BillingStatus.UNBILLED,
        )
        if created:
            recorded.append(UsageType.LLM_OUTPUT_TOKENS.value)

    metrics = call.metrics if isinstance(call.metrics, dict) else {}
    tx_seconds = metrics.get("transcription_seconds")
    if isinstance(tx_seconds, (int, float)) and tx_seconds > 0:
        qty = math.ceil(float(tx_seconds))
        _, created = ledger.record(
            tenant_id=call.tenant_id,
            usage_type=UsageType.TRANSCRIPTION,
            quantity=qty,
            idempotency_key=f"transcription:call:{call_id}",
            source_type="call",
            source_id=call_id,
            occurred_at=occurred,
            provider=str(metrics.get("transcription_provider") or "unknown"),
            usage_provenance=AccountingProvenance.ACTUAL_PROVIDER,
            cost_provenance=AccountingProvenance.CONFIGURED_RATE,
            billing_status=BillingStatus.UNBILLED,
        )
        if created:
            recorded.append(UsageType.TRANSCRIPTION.value)

    return recorded


def ingest_tool_call(
    session: Session,
    *,
    tenant_id: UUID,
    tool_name: str,
    operation_id: UUID | None,
    call_id: UUID | None,
    ok: bool,
    error_code: str | None,
    occurred_at: datetime | None = None,
) -> bool:
    """Count tool executions (no fabricated internal tool COGS)."""
    if operation_id is not None:
        key = f"tool:{tool_name}:{operation_id}"
        source_id = str(operation_id)
    elif call_id is not None:
        key = f"tool:{tool_name}:call:{call_id}"
        source_id = str(call_id)
    else:
        return False

    ledger = UsageLedgerService(session)
    _, created = ledger.record(
        tenant_id=tenant_id,
        usage_type=UsageType.TOOL_CALLS,
        quantity=1,
        idempotency_key=key,
        source_type="ai_tool",
        source_id=source_id,
        occurred_at=occurred_at,
        provider="platform",
        provider_reference=tool_name,
        usage_provenance=AccountingProvenance.ACTUAL_INTERNAL,
        cost_provenance=AccountingProvenance.UNAVAILABLE,
        cost_basis_override=CostBasis.NONE,
        billing_status=BillingStatus.UNBILLED,
        metadata={
            "tool": tool_name,
            "ok": ok,
            "error_code": error_code,
            "call_id": str(call_id) if call_id else None,
        },
    )
    return created


def ingest_sms_message(
    session: Session,
    message: SmsMessage,
    *,
    settings: Settings | None = None,
) -> bool:
    """Billable SMS = provider SENT/DELIVERED (not QUEUED/FAILED/retry alone)."""
    status = (message.status or "").upper()
    if status not in {"SENT", "DELIVERED", "ACCEPTED", "SUCCESS"}:
        return False

    ref = message.provider_message_id or str(message.id)
    ledger = UsageLedgerService(session, catalog=catalog_from_settings(settings))
    _, created = ledger.record(
        tenant_id=message.tenant_id,
        usage_type=UsageType.SMS,
        quantity=1,
        idempotency_key=f"sms:{ref}",
        source_type="sms_message",
        source_id=str(message.id),
        occurred_at=message.created_at or datetime.now(UTC),
        provider="twilio",
        provider_reference=ref,
        usage_provenance=AccountingProvenance.ACTUAL_PROVIDER,
        cost_provenance=AccountingProvenance.CONFIGURED_RATE,
        billing_status=BillingStatus.UNBILLED,
        metadata={
            "direction": message.direction,
            "status": message.status,
            "billable_event": "provider_sent_or_delivered",
        },
    )
    return created


def ingest_storage_snapshot(
    session: Session,
    tenant_id: UUID,
    *,
    billing_period: str | None = None,
    settings: Settings | None = None,
) -> int:
    """Periodic storage snapshot — one entry per tenant per billing period."""
    now = datetime.now(UTC)
    period = billing_period or f"{now.year:04d}-{now.month:02d}"
    total_bytes = int(
        session.scalar(
            select(func.coalesce(func.sum(RecordingObject.size_bytes), 0)).where(
                RecordingObject.tenant_id == tenant_id
            )
        )
        or 0
    )
    ledger = UsageLedgerService(session, catalog=catalog_from_settings(settings))
    catalog = catalog_from_settings(settings)
    price = catalog.resolve(UsageType.STORAGE)
    cost_prov = (
        AccountingProvenance.CONFIGURED_RATE
        if price.unit_cost_micros is not None
        else AccountingProvenance.UNAVAILABLE
    )
    ledger.record(
        tenant_id=tenant_id,
        usage_type=UsageType.STORAGE,
        quantity=total_bytes,
        idempotency_key=f"storage:period:{period}",
        source_type="storage_snapshot",
        source_id=period,
        occurred_at=now,
        provider=str(
            getattr(settings or get_settings(), "object_storage_backend", "fs")
        ),
        usage_provenance=AccountingProvenance.ACTUAL_INTERNAL,
        cost_provenance=cost_prov,
        billing_status=BillingStatus.UNBILLED,
        metadata={"bytes": total_bytes, "snapshot_at": now.isoformat()},
    )
    return total_bytes


def ingest_infrastructure_period(
    session: Session,
    tenant_id: UUID,
    *,
    billing_period: str | None = None,
    settings: Settings | None = None,
) -> bool:
    """Allocate configured infrastructure cost once per period — or skip (UNAVAILABLE)."""
    now = datetime.now(UTC)
    period = billing_period or f"{now.year:04d}-{now.month:02d}"
    ledger = UsageLedgerService(session, catalog=catalog_from_settings(settings))
    price = ledger._catalog.resolve(UsageType.INFRASTRUCTURE)
    if price.unit_cost_micros is None:
        # Do not write a $0 row — missing allocation must stay UNAVAILABLE.
        return False
    _, created = ledger.record(
        tenant_id=tenant_id,
        usage_type=UsageType.INFRASTRUCTURE,
        quantity=1,
        idempotency_key=f"infra:period:{period}",
        source_type="infrastructure_allocation",
        source_id=period,
        occurred_at=now,
        provider="configured",
        usage_provenance=AccountingProvenance.ALLOCATED_COST,
        cost_provenance=AccountingProvenance.ALLOCATED_COST,
        cost_basis_override=CostBasis.ALLOCATED,
        unit_cost_micros_override=price.unit_cost_micros,
        total_cost_micros_override=price.unit_cost_micros,
        billing_status=BillingStatus.UNBILLED,
        metadata={"note": "Configured allocation — not a vendor invoice"},
    )
    return created


def _token_sum(usage: dict[str, Any], keys: tuple[str, ...]) -> int:
    if keys and keys[0] in {"input_tokens", "output_tokens"}:
        agg = usage.get(keys[0])
        if isinstance(agg, (int, float)) and not isinstance(agg, bool):
            return max(0, int(agg))
    total = 0
    for key in (
        keys[1:] if keys and keys[0] in {"input_tokens", "output_tokens"} else keys
    ):
        raw = usage.get(key)
        if isinstance(raw, bool):
            continue
        if isinstance(raw, (int, float)) and raw > 0:
            total += int(raw)
    return total
