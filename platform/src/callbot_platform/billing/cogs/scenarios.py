"""Modeled COGS scenarios for scale / sensitivity / Ship vs Scale."""

from __future__ import annotations

from typing import Any

from callbot_platform.billing.cogs.calculator import (
    apply_livekit_agent_included_bucket,
    estimate_call_cogs,
)
from callbot_platform.billing.cogs.rates import CogsRates
from callbot_platform.billing.cogs.types import (
    CHANNEL_PSTN_SIP,
    TRANSFER_NONE,
    CallCogsInput,
)

DEFAULT_SCALE_MINUTES: tuple[int, ...] = (1_000, 10_000, 100_000)


def _variable_breakdown(estimate_dict: dict[str, Any]) -> dict[str, float]:
    return {
        "openai_usd": float(estimate_dict["openai_cost_usd"]),
        "livekit_agent_usd": float(estimate_dict["livekit_agent_cost_usd"]),
        "livekit_sip_usd": float(estimate_dict["livekit_sip_cost_usd"]),
        "livekit_bvc_usd": float(estimate_dict["livekit_bvc_cost_usd"]),
        "twilio_origination_usd": float(estimate_dict["twilio_origination_cost_usd"]),
        "twilio_termination_usd": float(estimate_dict["twilio_termination_cost_usd"]),
        "total_variable_usd": float(estimate_dict["total_estimated_cogs_usd"]),
    }


def _fixed_costs(rates: CogsRates) -> dict[str, float]:
    return {
        "livekit_fixed_monthly_usd": rates.livekit_fixed_monthly_usd,
        "phone_rental_monthly_usd": rates.phone_rental_monthly_usd,
        "sms_monthly_usd": rates.sms_monthly_usd,
        "total_fixed_monthly_usd": (
            rates.livekit_fixed_monthly_usd
            + rates.phone_rental_monthly_usd
            + rates.sms_monthly_usd
        ),
    }


def scale_minute_scenarios(
    rates: CogsRates,
    *,
    minutes: tuple[int, ...] = DEFAULT_SCALE_MINUTES,
    channel: str = CHANNEL_PSTN_SIP,
    transfer_kind: str = TRANSFER_NONE,
    openai_per_minute: float | None = None,
) -> list[dict[str, Any]]:
    """Modeled PSTN (default) COGS for N vendor minutes — not live usage data."""
    results: list[dict[str, Any]] = []
    for minute_count in minutes:
        seconds = int(minute_count) * 60
        estimate = estimate_call_cogs(
            CallCogsInput(
                billable_seconds=seconds,
                channel=channel,  # type: ignore[arg-type]
                transfer_kind=transfer_kind,  # type: ignore[arg-type]
                openai_usage=None,
            ),
            rates,
            openai_per_minute_override=openai_per_minute,
        )
        payload = estimate.as_dict()
        agent_adj = apply_livekit_agent_included_bucket(
            agent_cost_usd=estimate.livekit_agent_cost_usd,
            vendor_minutes=estimate.vendor_minutes,
            rates=rates,
        )
        variable = _variable_breakdown(payload)
        variable_after_included = (
            variable["total_variable_usd"]
            - agent_adj["agent_cost_before_included_usd"]
            + agent_adj["agent_cost_after_included_usd"]
        )
        fixed = _fixed_costs(rates)
        results.append(
            {
                "minutes": minute_count,
                "channel": channel,
                "transfer_kind": transfer_kind,
                "openai_per_minute_usd": (
                    openai_per_minute
                    if openai_per_minute is not None
                    else rates.openai_per_minute_usd
                ),
                "livekit_plan": rates.livekit_plan,
                "variable": variable,
                "livekit_agent_included_adjustment": agent_adj,
                "variable_after_agent_included_usd": variable_after_included,
                "fixed_monthly": fixed,
                "notes": [
                    "modeled_scenario",
                    "uses_fractional_vendor_minutes",
                    "openai_per_minute_estimate",
                    *list(estimate.notes),
                ],
            }
        )
    return results


def openai_sensitivity_scenarios(rates: CogsRates) -> dict[str, Any]:
    rates_list = (
        ("low", rates.openai_sensitivity_low_usd),
        ("base", rates.openai_per_minute_usd),
        ("high", rates.openai_sensitivity_high_usd),
    )
    return {
        "label": "openai_per_minute_sensitivity",
        "scenarios": {
            name: scale_minute_scenarios(rates, openai_per_minute=rate)
            for name, rate in rates_list
        },
    }


def ship_vs_scale_scenarios(rates: CogsRates) -> dict[str, Any]:
    return {
        "label": "livekit_ship_vs_scale",
        "ship": scale_minute_scenarios(rates.with_livekit_plan("ship")),
        "scale": scale_minute_scenarios(rates.with_livekit_plan("scale")),
    }


def full_scenario_report(rates: CogsRates) -> dict[str, Any]:
    return {
        "scale_minutes": scale_minute_scenarios(rates),
        "openai_sensitivity": openai_sensitivity_scenarios(rates),
        "ship_vs_scale": ship_vs_scale_scenarios(rates),
        "fixed_monthly": _fixed_costs(rates),
        "assumptions": [
            "Variable COGS uses fractional vendor minutes (billable_seconds/60).",
            "Customer billable minutes remain ceil-based and separate.",
            "Browser/WebRTC excludes Twilio and LiveKit SIP.",
            "Included customer plan minutes still incur full variable COGS.",
            "LiveKit agent included bucket applied only in scenario/fleet views.",
            "OpenAI token billing used when session usage is present; else $/min.",
            "Warm transfer termination duration is estimated, not from CDRs.",
            "Phone rental and SMS are fixed monthly costs, not voice-minute COGS.",
        ],
    }
