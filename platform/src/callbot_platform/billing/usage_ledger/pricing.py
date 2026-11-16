"""Versioned pricing resolver — snapshot rates at usage time."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from callbot_platform.billing.cogs.rates import CogsRates, rates_from_settings
from callbot_platform.billing.usage_ledger.categories import CostBasis, UsageType
from callbot_platform.billing.usage_ledger.money import usd_to_micros
from callbot_platform.config import Settings, get_settings

PRICING_VERSION = "usage-pricing-v1"


@dataclass(frozen=True, slots=True)
class ResolvedPrice:
    pricing_version: str
    unit_cost_micros: int | None
    cost_basis: CostBasis
    currency: str
    snapshot: dict[str, Any]


@dataclass(frozen=True, slots=True)
class UsagePricingCatalog:
    """Configured unit costs — not live vendor invoices unless marked observed."""

    version: str
    currency: str
    # Per-minute voice vendor bundle estimate (configured).
    voice_per_minute_micros: int | None
    # Per 1M tokens → per-token micros derived at resolve time from CogsRates.
    llm_input_per_1m_usd: Decimal
    llm_output_per_1m_usd: Decimal
    sms_per_message_micros: int | None
    transcription_per_second_micros: int | None
    storage_per_gb_month_micros: int | None
    infrastructure_period_micros: int | None
    rates_snapshot: dict[str, Any]

    def resolve(
        self,
        usage_type: UsageType,
        *,
        at: datetime | None = None,
    ) -> ResolvedPrice:
        _ = at  # reserved for historical effective ranges
        snap = {
            "pricing_version": self.version,
            "currency": self.currency,
            "rates": self.rates_snapshot,
            "estimated": True,
        }
        if usage_type == UsageType.VOICE_MINUTES:
            return ResolvedPrice(
                pricing_version=self.version,
                unit_cost_micros=self.voice_per_minute_micros,
                cost_basis=(
                    CostBasis.CONFIGURED
                    if self.voice_per_minute_micros is not None
                    else CostBasis.NONE
                ),
                currency=self.currency,
                snapshot=snap,
            )
        if usage_type == UsageType.LLM_INPUT_TOKENS:
            per_token = usd_to_micros(self.llm_input_per_1m_usd / Decimal(1_000_000))
            return ResolvedPrice(
                pricing_version=self.version,
                unit_cost_micros=per_token if per_token > 0 else None,
                cost_basis=CostBasis.CONFIGURED if per_token > 0 else CostBasis.NONE,
                currency=self.currency,
                snapshot=snap,
            )
        if usage_type == UsageType.LLM_OUTPUT_TOKENS:
            per_token = usd_to_micros(self.llm_output_per_1m_usd / Decimal(1_000_000))
            return ResolvedPrice(
                pricing_version=self.version,
                unit_cost_micros=per_token if per_token > 0 else None,
                cost_basis=CostBasis.CONFIGURED if per_token > 0 else CostBasis.NONE,
                currency=self.currency,
                snapshot=snap,
            )
        if usage_type == UsageType.SMS:
            return ResolvedPrice(
                pricing_version=self.version,
                unit_cost_micros=self.sms_per_message_micros,
                cost_basis=(
                    CostBasis.CONFIGURED
                    if self.sms_per_message_micros is not None
                    else CostBasis.NONE
                ),
                currency=self.currency,
                snapshot=snap,
            )
        if usage_type == UsageType.TRANSCRIPTION:
            return ResolvedPrice(
                pricing_version=self.version,
                unit_cost_micros=self.transcription_per_second_micros,
                cost_basis=(
                    CostBasis.CONFIGURED
                    if self.transcription_per_second_micros is not None
                    else CostBasis.NONE
                ),
                currency=self.currency,
                snapshot=snap,
            )
        if usage_type == UsageType.STORAGE:
            return ResolvedPrice(
                pricing_version=self.version,
                unit_cost_micros=self.storage_per_gb_month_micros,
                cost_basis=(
                    CostBasis.CONFIGURED
                    if self.storage_per_gb_month_micros is not None
                    else CostBasis.NONE
                ),
                currency=self.currency,
                snapshot=snap,
            )
        if usage_type == UsageType.INFRASTRUCTURE:
            return ResolvedPrice(
                pricing_version=self.version,
                unit_cost_micros=self.infrastructure_period_micros,
                cost_basis=(
                    CostBasis.ALLOCATED
                    if self.infrastructure_period_micros is not None
                    else CostBasis.NONE
                ),
                currency=self.currency,
                snapshot=snap,
            )
        # AI_REQUESTS / TOOL_CALLS — counts only unless a billable provider cost exists.
        return ResolvedPrice(
            pricing_version=self.version,
            unit_cost_micros=None,
            cost_basis=CostBasis.NONE,
            currency=self.currency,
            snapshot=snap,
        )


def catalog_from_rates(
    rates: CogsRates, *, settings: Settings | None = None
) -> UsagePricingCatalog:
    settings = settings or get_settings()
    # Voice per-minute: sum of primary configured vendor minute rates (estimate).
    voice_usd = Decimal(str(rates.openai_per_minute_usd)) + Decimal(
        str(rates.livekit_agent_per_minute_usd)
    )
    voice_micros = usd_to_micros(voice_usd) if voice_usd > 0 else None

    sms_per_msg = getattr(settings, "cogs_sms_per_message_usd", None)
    sms_micros: int | None = None
    if sms_per_msg is not None and float(sms_per_msg) > 0:
        sms_micros = usd_to_micros(sms_per_msg)

    transcription = getattr(settings, "cogs_transcription_per_minute_usd", None)
    transcription_micros: int | None = None
    if transcription is not None and float(transcription) > 0:
        # Store per-second from per-minute rate.
        transcription_micros = usd_to_micros(Decimal(str(transcription)) / Decimal(60))

    storage_gb = getattr(settings, "cogs_storage_per_gb_month_usd", None)
    storage_micros: int | None = None
    if storage_gb is not None and float(storage_gb) > 0:
        storage_micros = usd_to_micros(storage_gb)

    infra_total = (
        Decimal(str(rates.livekit_fixed_monthly_usd))
        + Decimal(str(rates.phone_rental_monthly_usd))
        + Decimal(str(rates.sms_monthly_usd))
    )
    infra_micros = usd_to_micros(infra_total) if infra_total > 0 else None

    return UsagePricingCatalog(
        version=PRICING_VERSION,
        currency="usd",
        voice_per_minute_micros=voice_micros,
        llm_input_per_1m_usd=Decimal(str(rates.openai_text_input_per_1m_usd)),
        llm_output_per_1m_usd=Decimal(str(rates.openai_text_output_per_1m_usd)),
        sms_per_message_micros=sms_micros,
        transcription_per_second_micros=transcription_micros,
        storage_per_gb_month_micros=storage_micros,
        infrastructure_period_micros=infra_micros,
        rates_snapshot=rates.snapshot(),
    )


def catalog_from_settings(settings: Settings | None = None) -> UsagePricingCatalog:
    settings = settings or get_settings()
    return catalog_from_rates(rates_from_settings(settings), settings=settings)
