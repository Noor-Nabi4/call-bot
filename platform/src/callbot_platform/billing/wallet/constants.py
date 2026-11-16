"""Wallet constants."""

from __future__ import annotations

WALLET_CURRENCY = "USD"

TOPUP_PRESETS_CENTS: tuple[int, ...] = (
    1000,
    2500,
    5000,
    10000,
    25000,
)

MIN_TOPUP_CENTS = 500  # $5
MAX_TOPUP_CENTS = 500_000  # $5,000

DEFAULT_LOW_BALANCE_CENTS = 2000
DEFAULT_CRITICAL_BALANCE_CENTS = 500

# Max unpaid exposure for an in-progress call (cents).
IN_PROGRESS_EXPOSURE_CENTS = 500

GRACE_PERIOD_DAYS = 3
