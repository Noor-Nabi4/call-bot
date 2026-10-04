"""Internal COGS estimation for AI voice calls (not customer billing)."""

from __future__ import annotations

from callbot_platform.billing.cogs.calculator import estimate_call_cogs, usd_to_micros
from callbot_platform.billing.cogs.rates import CogsRates, rates_from_settings
from callbot_platform.billing.cogs.scenarios import (
    openai_sensitivity_scenarios,
    scale_minute_scenarios,
    ship_vs_scale_scenarios,
)
from callbot_platform.billing.cogs.service import CogsService
from callbot_platform.billing.cogs.types import (
    CHANNEL_BROWSER_WEBRTC,
    CHANNEL_PSTN_SIP,
    OPENAI_SOURCE_PER_MINUTE,
    OPENAI_SOURCE_TOKEN,
    TRANSFER_COLD,
    TRANSFER_NONE,
    TRANSFER_WARM,
    CallCogsEstimate,
    CallCogsInput,
)

__all__ = [
    "CHANNEL_BROWSER_WEBRTC",
    "CHANNEL_PSTN_SIP",
    "OPENAI_SOURCE_PER_MINUTE",
    "OPENAI_SOURCE_TOKEN",
    "TRANSFER_COLD",
    "TRANSFER_NONE",
    "TRANSFER_WARM",
    "CallCogsEstimate",
    "CallCogsInput",
    "CogsRates",
    "CogsService",
    "estimate_call_cogs",
    "openai_sensitivity_scenarios",
    "rates_from_settings",
    "scale_minute_scenarios",
    "ship_vs_scale_scenarios",
    "usd_to_micros",
]
