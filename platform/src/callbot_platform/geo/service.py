"""Geo catalog service — list + validate business-profile geo fields."""

from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from callbot_platform.geo.cache import get_cached_catalog, set_cached_catalog
from callbot_platform.geo.currency_display import currency_symbol as _currency_symbol
from callbot_platform.geo.repos import GeoCatalogRepository


class GeoCatalogError(Exception):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class GeoCatalogService:
    def __init__(self, session: Session) -> None:
        self._repo = GeoCatalogRepository(session)

    def catalog_payload(self) -> dict[str, Any]:
        cached = get_cached_catalog()
        if cached is not None:
            return cached
        payload = {
            "countries": [
                {
                    "key": c.code,
                    "name": c.name,
                    "default_currency_code": c.default_currency_code,
                }
                for c in self._repo.list_countries()
            ],
            "currencies": [
                {
                    "key": c.code,
                    "name": c.name,
                    "symbol": _currency_symbol(c.code),
                }
                for c in self._repo.list_currencies()
            ],
            "timezones": [
                {"key": t.name, "name": t.label} for t in self._repo.list_timezones()
            ],
        }
        set_cached_catalog(payload)
        return payload

    def regions_payload(self, country_code: str) -> dict[str, Any]:
        code = (country_code or "").strip().upper()
        if not code:
            raise GeoCatalogError("invalid_country", "Country is required")
        country = self._repo.get_country(code)
        if country is None or not country.is_active:
            raise GeoCatalogError("unknown_country", "Unknown country")
        return {
            "country": code,
            "regions": [
                {"key": r.code, "name": r.name} for r in self._repo.list_regions(code)
            ],
        }

    def normalize_and_validate_profile_fields(
        self,
        *,
        country: str | None = None,
        state: str | None = None,
        currency: str | None = None,
        timezone: str | None = None,
        existing_country: str | None = None,
    ) -> dict[str, str | None]:
        """Normalize codes and validate against catalog. Blank clears the field."""
        out: dict[str, str | None] = {}

        country_code: str | None = None
        if country is not None:
            cleaned = country.strip()
            if not cleaned:
                out["country"] = None
            else:
                if len(cleaned) == 2:
                    country_code = cleaned.upper()
                else:
                    match = self._repo.find_country_by_name(cleaned)
                    country_code = match.code if match else cleaned[:2].upper()
                row = self._repo.get_country(country_code)
                if row is None or not row.is_active:
                    raise GeoCatalogError(
                        "unknown_country",
                        "Select a valid country",
                    )
                out["country"] = country_code

        if currency is not None:
            cleaned = currency.strip().upper()
            if not cleaned:
                out["currency"] = None
            else:
                code = cleaned[:3]
                row = self._repo.get_currency(code)
                if row is None or not row.is_active:
                    raise GeoCatalogError(
                        "unknown_currency",
                        "Select a valid currency",
                    )
                out["currency"] = code

        if timezone is not None:
            cleaned = timezone.strip()
            if not cleaned:
                out["timezone"] = None
            else:
                row = self._repo.get_timezone(cleaned)
                if row is None or not row.is_active:
                    raise GeoCatalogError(
                        "unknown_timezone",
                        "Select a valid timezone",
                    )
                out["timezone"] = cleaned

        if state is not None:
            cleaned = state.strip()
            if not cleaned:
                out["state"] = None
            else:
                cc = country_code or out.get("country")
                if not isinstance(cc, str) or not cc:
                    prior = (existing_country or "").strip().upper()
                    cc = prior or None
                if isinstance(cc, str) and cc:
                    by_code = self._repo.get_region(cc, cleaned)
                    if by_code is not None and by_code.is_active:
                        out["state"] = by_code.code
                    else:
                        by_name = self._repo.find_region_by_name(cc, cleaned)
                        if by_name is not None:
                            out["state"] = by_name.code
                        elif self._repo.has_regions(cc):
                            raise GeoCatalogError(
                                "unknown_region",
                                "Select a valid state / province",
                            )
                        else:
                            out["state"] = cleaned
                else:
                    out["state"] = cleaned

        return out
