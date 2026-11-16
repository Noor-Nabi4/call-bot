"""Idempotent geo catalog seeder."""

from __future__ import annotations

import json
import logging
from importlib import resources
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.geo import (
    GeoCountry,
    GeoCurrency,
    GeoRegion,
    GeoTimezone,
)

logger = logging.getLogger(__name__)


def _load_json(name: str) -> list[dict[str, Any]]:
    root = resources.files("callbot_platform.geo.data")
    raw = (root / name).read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, list):
        raise ValueError(f"geo seed {name} must be a JSON array")
    return data


def ensure_geo_catalog(session: Session) -> dict[str, int]:
    """Upsert currencies → timezones → countries → regions. Safe to re-run."""
    currencies = _load_json("currencies.json")
    timezones = _load_json("timezones.json")
    countries = _load_json("countries.json")
    regions = _load_json("regions.json")

    currency_codes = {str(r["code"]).upper() for r in currencies}

    # Currencies first (countries FK).
    for row in currencies:
        code = str(row["code"]).upper()
        existing = session.get(GeoCurrency, code)
        if existing is None:
            session.add(GeoCurrency(code=code, name=str(row["name"]), is_active=True))
        else:
            existing.name = str(row["name"])
            existing.is_active = True

    for row in timezones:
        name = str(row["name"])
        existing = session.get(GeoTimezone, name)
        if existing is None:
            session.add(GeoTimezone(name=name, label=str(row["label"]), is_active=True))
        else:
            existing.label = str(row["label"])
            existing.is_active = True

    session.flush()

    for row in countries:
        code = str(row["code"]).upper()
        default_currency = row.get("default_currency_code")
        if default_currency:
            default_currency = str(default_currency).upper()
            if default_currency not in currency_codes:
                default_currency = None
        existing = session.get(GeoCountry, code)
        if existing is None:
            session.add(
                GeoCountry(
                    code=code,
                    name=str(row["name"]),
                    default_currency_code=default_currency,
                    sort_order=int(row.get("sort_order") or 0),
                    is_active=True,
                )
            )
        else:
            existing.name = str(row["name"])
            existing.default_currency_code = default_currency
            existing.sort_order = int(row.get("sort_order") or 0)
            existing.is_active = True

    session.flush()

    country_codes = set(session.scalars(select(GeoCountry.code)).all())

    # Regions: upsert by (country_code, code). Use ORM for SQLite test compat.
    upserted_regions = 0
    for row in regions:
        country_code = str(row["country_code"]).upper()
        if country_code not in country_codes:
            continue
        code = str(row["code"]).upper()
        name = str(row["name"])
        existing = session.scalar(
            select(GeoRegion).where(
                GeoRegion.country_code == country_code,
                GeoRegion.code == code,
            )
        )
        if existing is None:
            session.add(
                GeoRegion(
                    country_code=country_code,
                    code=code,
                    name=name,
                    is_active=True,
                )
            )
        else:
            existing.name = name
            existing.is_active = True
        upserted_regions += 1

    session.flush()
    counts = {
        "currencies": len(currencies),
        "timezones": len(timezones),
        "countries": len(countries),
        "regions": upserted_regions,
    }
    logger.info("geo catalog ensured: %s", counts)
    return counts


def main() -> None:
    from callbot_platform.db import get_session_factory

    factory = get_session_factory()
    with factory() as session:
        counts = ensure_geo_catalog(session)
        session.commit()
        print(counts)


if __name__ == "__main__":
    main()
