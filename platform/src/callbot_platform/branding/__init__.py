"""Tenant white-label branding repository."""

from __future__ import annotations

import re
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.branding import TenantBranding
from callbot_platform.telephony.audit import write_audit

_HEX = re.compile(r"^#[0-9A-Fa-f]{6}$")


class BrandingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class BrandingRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, tenant_id: UUID) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantBranding).where(TenantBranding.tenant_id == tenant_id)
        )
        if row is None:
            return self._empty(tenant_id)
        return self._serialize(row)

    def upsert(
        self,
        tenant_id: UUID,
        *,
        actor: str,
        product_name: str | None = None,
        logo_url: str | None = None,
        primary_color: str | None = None,
        accent_color: str | None = None,
        support_email: str | None = None,
    ) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantBranding).where(TenantBranding.tenant_id == tenant_id)
        )
        if row is None:
            row = TenantBranding(tenant_id=tenant_id)
            self._session.add(row)

        if product_name is not None:
            cleaned = product_name.strip()[:128]
            row.product_name = cleaned or None
        if logo_url is not None:
            row.logo_url = self._validate_logo_url(logo_url)
        if primary_color is not None:
            row.primary_color = self._validate_hex(primary_color, "primary_color")
        if accent_color is not None:
            row.accent_color = self._validate_hex(accent_color, "accent_color")
        if support_email is not None:
            email = support_email.strip()[:255]
            if email and "@" not in email:
                raise BrandingError("invalid_support_email", "support_email is invalid")
            row.support_email = email or None

        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="tenant_branding_updated",
            resource_ids={"tenant_id": str(tenant_id)},
            payload_summary={
                "product_name": row.product_name,
                "has_logo": bool(row.logo_url),
            },
        )
        return self._serialize(row)

    def _validate_hex(self, value: str, field: str) -> str | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        if not _HEX.match(cleaned):
            raise BrandingError(
                "invalid_color", f"{field} must be a hex color like #1f6f5b"
            )
        return cleaned.lower()

    def _validate_logo_url(self, value: str) -> str | None:
        cleaned = value.strip()
        if not cleaned:
            return None
        if len(cleaned) > 2048:
            raise BrandingError("invalid_logo_url", "logo_url is too long")
        parsed = urlparse(cleaned)
        if parsed.scheme not in {"https", "http"}:
            raise BrandingError("invalid_logo_url", "logo_url must be an http(s) URL")
        if not parsed.netloc:
            raise BrandingError("invalid_logo_url", "logo_url host is required")
        return cleaned

    def _empty(self, tenant_id: UUID) -> dict[str, Any]:
        return {
            "tenant_id": str(tenant_id),
            "product_name": None,
            "logo_url": None,
            "primary_color": None,
            "accent_color": None,
            "support_email": None,
            "updated_at": None,
        }

    def _serialize(self, row: TenantBranding) -> dict[str, Any]:
        return {
            "tenant_id": str(row.tenant_id),
            "product_name": row.product_name,
            "logo_url": row.logo_url,
            "primary_color": row.primary_color,
            "accent_color": row.accent_color,
            "support_email": row.support_email,
            "updated_at": row.updated_at.isoformat() if row.updated_at else None,
        }
