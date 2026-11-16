"""Tenant API key repository."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.api_keys import TenantApiKey
from callbot_platform.security.api_keys import (
    generate_api_key,
    hash_api_key,
    normalize_scopes,
)
from callbot_platform.telephony.audit import write_audit


class ApiKeyError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class ApiKeyRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_keys(self, tenant_id: UUID) -> list[dict[str, Any]]:
        rows = self._session.scalars(
            select(TenantApiKey)
            .where(TenantApiKey.tenant_id == tenant_id)
            .order_by(TenantApiKey.created_at.desc())
        ).all()
        return [self._serialize(r) for r in rows]

    def create_key(
        self,
        tenant_id: UUID,
        *,
        name: str,
        scopes: list[str] | None = None,
        notes: str | None = None,
        actor: str,
    ) -> dict[str, Any]:
        cleaned = (name or "").strip()
        if not cleaned:
            raise ApiKeyError("invalid_name", "Name is required")
        try:
            scope_list = normalize_scopes(scopes)
        except ValueError as exc:
            raise ApiKeyError("invalid_scopes", str(exc)) from exc

        active_count = len([k for k in self.list_keys(tenant_id) if k["is_active"]])
        if active_count >= 20:
            raise ApiKeyError("key_limit", "At most 20 active API keys per tenant")

        plaintext, prefix, digest = generate_api_key()
        row = TenantApiKey(
            tenant_id=tenant_id,
            name=cleaned[:128],
            key_prefix=prefix,
            key_hash=digest,
            scopes=scope_list,
            is_active=True,
            created_by=actor[:255],
            notes=(notes or "").strip()[:2000] or None,
        )
        self._session.add(row)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="api_key_created",
            resource_ids={"api_key_id": str(row.id), "prefix": prefix},
            payload_summary={"scopes": scope_list},
        )
        data = self._serialize(row)
        data["secret"] = plaintext
        return data

    def revoke_key(
        self, tenant_id: UUID, key_id: UUID, *, actor: str
    ) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantApiKey).where(
                TenantApiKey.id == key_id, TenantApiKey.tenant_id == tenant_id
            )
        )
        if row is None:
            raise ApiKeyError("not_found", "API key not found")
        if not row.is_active:
            return self._serialize(row)
        row.is_active = False
        row.revoked_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="api_key_revoked",
            resource_ids={"api_key_id": str(row.id)},
        )
        return self._serialize(row)

    def authenticate(self, plaintext: str) -> TenantApiKey | None:
        token = (plaintext or "").strip()
        if not token.startswith("cbk_") or len(token) < 20:
            return None
        digest = hash_api_key(token)
        row = self._session.scalar(
            select(TenantApiKey).where(
                TenantApiKey.key_hash == digest,
                TenantApiKey.is_active.is_(True),
            )
        )
        if row is None:
            return None
        row.last_used_at = datetime.now(UTC)
        self._session.flush()
        return row

    def _serialize(self, row: TenantApiKey) -> dict[str, Any]:
        return {
            "id": str(row.id),
            "name": row.name,
            "key_prefix": row.key_prefix,
            "scopes": list(row.scopes or []),
            "is_active": row.is_active,
            "created_by": row.created_by,
            "last_used_at": row.last_used_at.isoformat() if row.last_used_at else None,
            "revoked_at": row.revoked_at.isoformat() if row.revoked_at else None,
            "notes": row.notes,
            "created_at": row.created_at.isoformat() if row.created_at else None,
        }
