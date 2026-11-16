"""Cached seed JSON accessors (immutable reference data)."""

from __future__ import annotations

import json
from functools import lru_cache
from importlib import resources
from typing import Any


@lru_cache(maxsize=8)
def _raw_seed_json(name: str) -> str:
    root = resources.files("callbot_platform.geo.data")
    return (root / name).read_text(encoding="utf-8")


def load_seed_rows(name: str) -> list[dict[str, Any]]:
    data = json.loads(_raw_seed_json(name))
    if not isinstance(data, list):
        raise ValueError(f"geo seed {name} must be a JSON array")
    return data


@lru_cache(maxsize=1)
def currency_codes_from_seed() -> frozenset[str]:
    return frozenset(
        str(row["code"]).upper() for row in load_seed_rows("currencies.json")
    )


@lru_cache(maxsize=1)
def country_codes_from_seed() -> frozenset[str]:
    return frozenset(
        str(row["code"]).upper() for row in load_seed_rows("countries.json")
    )
