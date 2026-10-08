"""Usage category + accounting provenance registries."""

from __future__ import annotations

from enum import StrEnum


class UsageType(StrEnum):
    VOICE_MINUTES = "VOICE_MINUTES"
    LLM_INPUT_TOKENS = "LLM_INPUT_TOKENS"
    LLM_OUTPUT_TOKENS = "LLM_OUTPUT_TOKENS"
    AI_REQUESTS = "AI_REQUESTS"
    TOOL_CALLS = "TOOL_CALLS"
    SMS = "SMS"
    TRANSCRIPTION = "TRANSCRIPTION"
    STORAGE = "STORAGE"
    INFRASTRUCTURE = "INFRASTRUCTURE"


class CostBasis(StrEnum):
    """Legacy cost derivation flag stored on ledger rows (compat)."""

    OBSERVED = "observed"
    CONFIGURED = "configured"
    ALLOCATED = "allocated"
    NONE = "none"


class AccountingProvenance(StrEnum):
    """Explicit certainty for usage, cost, or revenue values."""

    ACTUAL_PROVIDER = "ACTUAL_PROVIDER"
    ACTUAL_INTERNAL = "ACTUAL_INTERNAL"
    CONFIGURED_RATE = "CONFIGURED_RATE"
    ALLOCATED_COST = "ALLOCATED_COST"
    ESTIMATED = "ESTIMATED"
    UNAVAILABLE = "UNAVAILABLE"


class BillingStatus(StrEnum):
    """Billable-usage lifecycle — usage detected != usage billed/paid."""

    UNBILLED = "UNBILLED"
    ESTIMATED = "ESTIMATED"
    INVOICED = "INVOICED"
    PAID = "PAID"
    VOIDED = "VOIDED"
    ADJUSTED = "ADJUSTED"


class UsageUnit(StrEnum):
    MINUTES = "minutes"
    TOKENS = "tokens"
    REQUESTS = "requests"
    CALLS = "calls"
    MESSAGES = "messages"
    SECONDS = "seconds"
    BYTES = "bytes"
    PERIOD = "period"


USAGE_TYPE_UNITS: dict[UsageType, UsageUnit] = {
    UsageType.VOICE_MINUTES: UsageUnit.MINUTES,
    UsageType.LLM_INPUT_TOKENS: UsageUnit.TOKENS,
    UsageType.LLM_OUTPUT_TOKENS: UsageUnit.TOKENS,
    UsageType.AI_REQUESTS: UsageUnit.REQUESTS,
    UsageType.TOOL_CALLS: UsageUnit.CALLS,
    UsageType.SMS: UsageUnit.MESSAGES,
    UsageType.TRANSCRIPTION: UsageUnit.SECONDS,
    UsageType.STORAGE: UsageUnit.BYTES,
    UsageType.INFRASTRUCTURE: UsageUnit.PERIOD,
}

COGS_USAGE_TYPES: frozenset[UsageType] = frozenset(
    {
        UsageType.VOICE_MINUTES,
        UsageType.LLM_INPUT_TOKENS,
        UsageType.LLM_OUTPUT_TOKENS,
        UsageType.SMS,
        UsageType.TRANSCRIPTION,
        UsageType.STORAGE,
        UsageType.INFRASTRUCTURE,
    }
)


def cost_basis_to_provenance(basis: CostBasis | str | None) -> AccountingProvenance:
    if basis is None:
        return AccountingProvenance.UNAVAILABLE
    key = CostBasis(basis)
    if key == CostBasis.OBSERVED:
        return AccountingProvenance.ACTUAL_PROVIDER
    if key == CostBasis.CONFIGURED:
        return AccountingProvenance.CONFIGURED_RATE
    if key == CostBasis.ALLOCATED:
        return AccountingProvenance.ALLOCATED_COST
    return AccountingProvenance.UNAVAILABLE


def provenance_to_cost_basis(prov: AccountingProvenance) -> CostBasis:
    if prov == AccountingProvenance.ACTUAL_PROVIDER:
        return CostBasis.OBSERVED
    if prov == AccountingProvenance.CONFIGURED_RATE:
        return CostBasis.CONFIGURED
    if prov == AccountingProvenance.ALLOCATED_COST:
        return CostBasis.ALLOCATED
    return CostBasis.NONE
