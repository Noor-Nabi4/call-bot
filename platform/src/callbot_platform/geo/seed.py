"""Idempotent geo catalog seeder."""

from __future__ import annotations

import logging
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.geo import (
    GeoCountry,
    GeoCurrency,
    GeoRegion,
    GeoTimezone,
)
from callbot_platform.geo.cache import clear_catalog_cache
from callbot_platform.geo.seed_data import load_seed_rows

logger = logging.getLogger(__name__)


def _load_json(name: str) -> list[dict[str, Any]]:
    """Compatibility wrapper used by organization validation / tests."""
    return load_seed_rows(name)


def ensure_geo_catalog(session: Session) -> dict[str, int]:
    """Upsert currencies → timezones → countries → regions. Safe to re-run."""
    currencies = load_seed_rows("currencies.json")
    timezones = load_seed_rows("timezones.json")
    countries = load_seed_rows("countries.json")
    regions = load_seed_rows("regions.json")

    currency_codes = {str(r["code"]).upper() for r in currencies}

    existing_currencies = {
        row.code: row for row in session.scalars(select(GeoCurrency)).all()
    }
    for row in currencies:
        code = str(row["code"]).upper()
        existing = existing_currencies.get(code)
        if existing is None:
            session.add(GeoCurrency(code=code, name=str(row["name"]), is_active=True))
        else:
            existing.name = str(row["name"])
            existing.is_active = True

    existing_timezones = {
        row.name: row for row in session.scalars(select(GeoTimezone)).all()
    }
    for row in timezones:
        name = str(row["name"])
        existing = existing_timezones.get(name)
        if existing is None:
            session.add(GeoTimezone(name=name, label=str(row["label"]), is_active=True))
        else:
            existing.label = str(row["label"])
            existing.is_active = True

    session.flush()

    existing_countries = {
        row.code: row for row in session.scalars(select(GeoCountry)).all()
    }
    for row in countries:
        code = str(row["code"]).upper()
        default_currency = row.get("default_currency_code")
        if default_currency:
            default_currency = str(default_currency).upper()
            if default_currency not in currency_codes:
                default_currency = None
        existing = existing_countries.get(code)
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

    existing_regions = {
        (row.country_code, row.code): row
        for row in session.scalars(select(GeoRegion)).all()
    }
    upserted_regions = 0
    for row in regions:
        country_code = str(row["country_code"]).upper()
        if country_code not in country_codes:
            continue
        code = str(row["code"]).upper()
        name = str(row["name"])
        existing = existing_regions.get((country_code, code))
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
    clear_catalog_cache()
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
