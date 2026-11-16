"""Geo catalog repository — global reference data (not tenant-scoped)."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.geo import (
    GeoCountry,
    GeoCurrency,
    GeoRegion,
    GeoTimezone,
)


class GeoCatalogRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_countries(self, *, active_only: bool = True) -> list[GeoCountry]:
        stmt = select(GeoCountry).order_by(GeoCountry.sort_order, GeoCountry.name)
        if active_only:
            stmt = stmt.where(GeoCountry.is_active.is_(True))
        return list(self._session.scalars(stmt).all())

    def list_currencies(self, *, active_only: bool = True) -> list[GeoCurrency]:
        stmt = select(GeoCurrency).order_by(GeoCurrency.code)
        if active_only:
            stmt = stmt.where(GeoCurrency.is_active.is_(True))
        return list(self._session.scalars(stmt).all())

    def list_timezones(self, *, active_only: bool = True) -> list[GeoTimezone]:
        stmt = select(GeoTimezone).order_by(GeoTimezone.name)
        if active_only:
            stmt = stmt.where(GeoTimezone.is_active.is_(True))
        return list(self._session.scalars(stmt).all())

    def list_regions(
        self, country_code: str, *, active_only: bool = True
    ) -> list[GeoRegion]:
        code = country_code.strip().upper()
        stmt = (
            select(GeoRegion)
            .where(GeoRegion.country_code == code)
            .order_by(GeoRegion.name)
        )
        if active_only:
            stmt = stmt.where(GeoRegion.is_active.is_(True))
        return list(self._session.scalars(stmt).all())

    def get_country(self, code: str) -> GeoCountry | None:
        return self._session.get(GeoCountry, code.strip().upper())

    def get_currency(self, code: str) -> GeoCurrency | None:
        return self._session.get(GeoCurrency, code.strip().upper())

    def get_timezone(self, name: str) -> GeoTimezone | None:
        return self._session.get(GeoTimezone, name.strip())

    def get_region(self, country_code: str, code: str) -> GeoRegion | None:
        return self._session.scalar(
            select(GeoRegion).where(
                GeoRegion.country_code == country_code.strip().upper(),
                GeoRegion.code == code.strip().upper(),
            )
        )

    def find_region_by_name(self, country_code: str, name: str) -> GeoRegion | None:
        needle = name.strip().lower()
        if not needle:
            return None
        regions = self.list_regions(country_code, active_only=True)
        for region in regions:
            if region.name.lower() == needle or region.code.lower() == needle:
                return region
        return None
