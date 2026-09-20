"""Per-call COGS calculator (estimated; not vendor invoices)."""

from __future__ import annotations

from typing import Any

from callbot_platform.billing.cogs.rates import CogsRates
from callbot_platform.billing.cogs.types import (
    CHANNEL_PSTN_SIP,
    OPENAI_SOURCE_PER_MINUTE,
    OPENAI_SOURCE_TOKEN,
    TRANSFER_COLD,
    TRANSFER_WARM,
    CallCogsEstimate,
    CallCogsInput,
)

_MICROS_PER_USD = 1_000_000


def usd_to_micros(usd: float) -> int:
    if usd <= 0:
        return 0
    return round(usd * _MICROS_PER_USD)


def micros_to_usd(micros: int) -> float:
    return float(micros) / _MICROS_PER_USD


def vendor_minutes_from_seconds(billable_seconds: int) -> float:
    """Fractional vendor minutes from platform billable_seconds.

    Intentionally does NOT use customer ceil-minute rounding.
    """
    if billable_seconds <= 0:
        return 0.0
    return float(billable_seconds) / 60.0


def _tokens_present(usage: dict[str, Any] | None) -> bool:
    if not usage:
        return False
    keys = (
        "input_tokens",
        "output_tokens",
        "input_audio_tokens",
        "input_text_tokens",
        "output_audio_tokens",
        "output_text_tokens",
        "input_cached_tokens",
        "input_cached_audio_tokens",
        "input_cached_text_tokens",
    )
    return any(int(usage.get(k) or 0) > 0 for k in keys)


def _token_count(usage: dict[str, Any], *keys: str) -> int:
    for key in keys:
        value = usage.get(key)
        if value is not None:
            try:
                return max(0, int(value))
            except (TypeError, ValueError):
                continue
    return 0


def openai_token_cost_usd(usage: dict[str, Any], rates: CogsRates) -> float:
    """Cost from cached vs uncached audio/text token categories when available."""
    audio_in = _token_count(usage, "input_audio_tokens")
    text_in = _token_count(usage, "input_text_tokens")
    audio_out = _token_count(usage, "output_audio_tokens")
    text_out = _token_count(usage, "output_text_tokens")
    cached_audio = _token_count(
        usage, "input_cached_audio_tokens", "input_cached_tokens"
    )
    cached_text = _token_count(usage, "input_cached_text_tokens")

    # If modality breakdown is missing, treat totals as text (conservative lower
    # bound) rather than inventing audio/text split.
    input_total = _token_count(usage, "input_tokens")
    output_total = _token_count(usage, "output_tokens")
    if audio_in == 0 and text_in == 0 and input_total > 0:
        text_in = max(0, input_total - cached_audio - cached_text)
    if audio_out == 0 and text_out == 0 and output_total > 0:
        text_out = output_total

    # Avoid double-counting cached tokens already included in input totals.
    uncached_audio = max(0, audio_in - cached_audio) if audio_in else 0
    uncached_text = max(0, text_in - cached_text) if text_in else 0
    if audio_in == 0 and text_in == 0 and input_total > 0:
        uncached_text = max(0, input_total - cached_audio - cached_text)

    cost = 0.0
    cost += (uncached_audio / 1_000_000.0) * rates.openai_audio_input_per_1m_usd
    cost += (cached_audio / 1_000_000.0) * rates.openai_audio_cached_input_per_1m_usd
    cost += (uncached_text / 1_000_000.0) * rates.openai_text_input_per_1m_usd
    cost += (cached_text / 1_000_000.0) * rates.openai_text_cached_input_per_1m_usd
    cost += (audio_out / 1_000_000.0) * rates.openai_audio_output_per_1m_usd
    cost += (text_out / 1_000_000.0) * rates.openai_text_output_per_1m_usd
    return cost


def estimate_call_cogs(
    data: CallCogsInput,
    rates: CogsRates,
    *,
    openai_per_minute_override: float | None = None,
) -> CallCogsEstimate:
    notes: list[str] = []
    seconds = max(0, int(data.billable_seconds))
    minutes = vendor_minutes_from_seconds(seconds)

    if seconds <= 0:
        notes.append("zero_or_invalid_duration")
        return CallCogsEstimate(
            billable_seconds=seconds,
            vendor_minutes=0.0,
            channel=data.channel,
            transfer_kind=data.transfer_kind,
            openai_cost_usd=0.0,
            livekit_agent_cost_usd=0.0,
            livekit_sip_cost_usd=0.0,
            livekit_bvc_cost_usd=0.0,
            twilio_origination_cost_usd=0.0,
            twilio_termination_cost_usd=0.0,
            total_estimated_cogs_usd=0.0,
            openai_cost_source=OPENAI_SOURCE_PER_MINUTE,
            openai_usage=data.openai_usage,
            rate_snapshot=rates.snapshot(),
            notes=tuple(notes),
        )

    openai_rate = (
        float(openai_per_minute_override)
        if openai_per_minute_override is not None
        else rates.openai_per_minute_usd
    )

    if _tokens_present(data.openai_usage):
        assert data.openai_usage is not None
        openai_cost = openai_token_cost_usd(data.openai_usage, rates)
        openai_source = OPENAI_SOURCE_TOKEN
        notes.append("openai_from_token_usage")
    else:
        openai_cost = minutes * openai_rate
        openai_source = OPENAI_SOURCE_PER_MINUTE
        notes.append("openai_from_per_minute_estimate")

    agent_cost = minutes * rates.livekit_agent_per_minute_usd

    is_pstn = data.channel == CHANNEL_PSTN_SIP
    sip_cost = 0.0
    bvc_cost = 0.0
    origination = 0.0
    termination = 0.0

    if is_pstn:
        sip_cost = minutes * rates.livekit_sip_per_minute_usd
        bvc_cost = minutes * rates.livekit_bvc_telephony_per_minute_usd
        origination = minutes * rates.twilio_us_local_origination_per_minute_usd
        notes.append("pstn_sip_twilio_and_livekit_sip_included")
    else:
        bvc_cost = minutes * rates.livekit_bvc_per_minute_usd
        notes.append("browser_webrtc_excludes_twilio_and_livekit_sip")

    if data.transfer_kind == TRANSFER_WARM:
        if rates.warm_transfer_termination_seconds is not None:
            term_seconds = max(0, int(rates.warm_transfer_termination_seconds))
        else:
            term_seconds = seconds
        term_minutes = vendor_minutes_from_seconds(term_seconds)
        termination = term_minutes * rates.twilio_termination_per_minute_usd
        # Outbound warm leg also incurs LiveKit third-party SIP (estimated).
        sip_cost += term_minutes * rates.livekit_sip_per_minute_usd
        notes.append(f"warm_transfer_termination_estimated:{term_seconds}s")
    elif data.transfer_kind == TRANSFER_COLD:
        notes.append("cold_transfer_no_observed_termination_minutes")

    total = openai_cost + agent_cost + sip_cost + bvc_cost + origination + termination

    return CallCogsEstimate(
        billable_seconds=seconds,
        vendor_minutes=minutes,
        channel=data.channel,
        transfer_kind=data.transfer_kind,
        openai_cost_usd=openai_cost,
        livekit_agent_cost_usd=agent_cost,
        livekit_sip_cost_usd=sip_cost,
        livekit_bvc_cost_usd=bvc_cost,
        twilio_origination_cost_usd=origination,
        twilio_termination_cost_usd=termination,
        total_estimated_cogs_usd=total,
        openai_cost_source=openai_source,
        openai_usage=data.openai_usage,
        rate_snapshot=rates.snapshot(),
        notes=tuple(notes),
    )


def apply_livekit_agent_included_bucket(
    *,
    agent_cost_usd: float,
    vendor_minutes: float,
    rates: CogsRates,
) -> dict[str, float]:
    """Fleet-level adjustment for LiveKit agent included minutes (reporting only)."""
    included = float(rates.livekit_agent_included_minutes_monthly)
    if included <= 0 or vendor_minutes <= 0:
        return {
            "agent_cost_before_included_usd": agent_cost_usd,
            "agent_cost_after_included_usd": agent_cost_usd,
            "included_minutes_applied": 0.0,
        }
    billable_overage = max(0.0, vendor_minutes - included)
    after = billable_overage * rates.livekit_agent_per_minute_usd
    return {
        "agent_cost_before_included_usd": agent_cost_usd,
        "agent_cost_after_included_usd": after,
        "included_minutes_applied": min(included, vendor_minutes),
    }
