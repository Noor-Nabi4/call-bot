"""Configurable vendor rates for COGS estimates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Literal

from callbot_platform.config import Settings

LiveKitPlan = Literal["ship", "scale"]


@dataclass(frozen=True)
class CogsRates:
    openai_per_minute_usd: float
    openai_sensitivity_low_usd: float
    openai_sensitivity_high_usd: float
    openai_audio_input_per_1m_usd: float
    openai_audio_cached_input_per_1m_usd: float
    openai_audio_output_per_1m_usd: float
    openai_text_input_per_1m_usd: float
    openai_text_cached_input_per_1m_usd: float
    openai_text_output_per_1m_usd: float
    livekit_agent_per_minute_usd: float
    livekit_agent_included_minutes_monthly: int
    livekit_plan: LiveKitPlan
    livekit_sip_ship_per_minute_usd: float
    livekit_sip_scale_per_minute_usd: float
    livekit_bvc_telephony_per_minute_usd: float
    livekit_bvc_per_minute_usd: float
    twilio_us_local_origination_per_minute_usd: float
    twilio_termination_per_minute_usd: float
    warm_transfer_termination_seconds: int | None
    livekit_fixed_monthly_usd: float
    phone_rental_monthly_usd: float
    sms_monthly_usd: float

    @property
    def livekit_sip_per_minute_usd(self) -> float:
        if self.livekit_plan == "scale":
            return self.livekit_sip_scale_per_minute_usd
        return self.livekit_sip_ship_per_minute_usd

    def snapshot(self) -> dict[str, Any]:
        data = asdict(self)
        data["livekit_sip_per_minute_usd"] = self.livekit_sip_per_minute_usd
        data["estimated"] = True
        data["vendor_duration_basis"] = "billable_seconds / 60.0 (fractional)"
        data["customer_billing_basis"] = (
            "ceil(sum billable_seconds) then ceil(/60) — separate from COGS"
        )
        return data

    def with_livekit_plan(self, plan: LiveKitPlan) -> CogsRates:
        return CogsRates(
            **{
                **asdict(self),
                "livekit_plan": plan,
            }
        )

    def with_openai_per_minute(self, rate: float) -> CogsRates:
        return CogsRates(
            **{
                **asdict(self),
                "openai_per_minute_usd": rate,
            }
        )


def _normalize_livekit_plan(raw: str) -> LiveKitPlan:
    value = (raw or "ship").strip().lower()
    if value == "scale":
        return "scale"
    return "ship"


def rates_from_settings(settings: Settings) -> CogsRates:
    return CogsRates(
        openai_per_minute_usd=float(settings.cogs_openai_per_minute_usd),
        openai_sensitivity_low_usd=float(settings.cogs_openai_sensitivity_low_usd),
        openai_sensitivity_high_usd=float(settings.cogs_openai_sensitivity_high_usd),
        openai_audio_input_per_1m_usd=float(
            settings.cogs_openai_audio_input_per_1m_usd
        ),
        openai_audio_cached_input_per_1m_usd=float(
            settings.cogs_openai_audio_cached_input_per_1m_usd
        ),
        openai_audio_output_per_1m_usd=float(
            settings.cogs_openai_audio_output_per_1m_usd
        ),
        openai_text_input_per_1m_usd=float(settings.cogs_openai_text_input_per_1m_usd),
        openai_text_cached_input_per_1m_usd=float(
            settings.cogs_openai_text_cached_input_per_1m_usd
        ),
        openai_text_output_per_1m_usd=float(
            settings.cogs_openai_text_output_per_1m_usd
        ),
        livekit_agent_per_minute_usd=float(settings.cogs_livekit_agent_per_minute_usd),
        livekit_agent_included_minutes_monthly=max(
            0, int(settings.cogs_livekit_agent_included_minutes_monthly)
        ),
        livekit_plan=_normalize_livekit_plan(settings.cogs_livekit_plan),
        livekit_sip_ship_per_minute_usd=float(
            settings.cogs_livekit_sip_ship_per_minute_usd
        ),
        livekit_sip_scale_per_minute_usd=float(
            settings.cogs_livekit_sip_scale_per_minute_usd
        ),
        livekit_bvc_telephony_per_minute_usd=float(
            settings.cogs_livekit_bvc_telephony_per_minute_usd
        ),
        livekit_bvc_per_minute_usd=float(settings.cogs_livekit_bvc_per_minute_usd),
        twilio_us_local_origination_per_minute_usd=float(
            settings.cogs_twilio_us_local_origination_per_minute_usd
        ),
        twilio_termination_per_minute_usd=float(
            settings.cogs_twilio_termination_per_minute_usd
        ),
        warm_transfer_termination_seconds=settings.cogs_warm_transfer_termination_seconds,
        livekit_fixed_monthly_usd=float(settings.cogs_livekit_fixed_monthly_usd),
        phone_rental_monthly_usd=float(settings.cogs_phone_rental_monthly_usd),
        sms_monthly_usd=float(settings.cogs_sms_monthly_usd),
    )
