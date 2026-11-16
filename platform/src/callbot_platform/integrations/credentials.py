"""Encrypted credential store for integrations (never log or return plaintext)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.integrations import IntegrationCredential
from callbot_platform.security.crypto import CredentialCipher


class IntegrationCredentialStore:
    def __init__(self, session: Session, cipher: CredentialCipher) -> None:
        self._session = session
        self._cipher = cipher

    def upsert(
        self,
        *,
        tenant_id: UUID,
        integration_id: UUID,
        access_token: str | None = None,
        refresh_token: str | None = None,
        token_type: str | None = None,
        scope: str | None = None,
        expires_at: datetime | None = None,
        extra: dict[str, Any] | None = None,
    ) -> IntegrationCredential:
        row = self._session.scalar(
            select(IntegrationCredential).where(
                IntegrationCredential.tenant_id == tenant_id,
                IntegrationCredential.integration_id == integration_id,
            )
        )
        if row is None:
            row = IntegrationCredential(
                tenant_id=tenant_id, integration_id=integration_id
            )
            self._session.add(row)

        if access_token is not None:
            row.access_token_enc = self._cipher.encrypt(access_token)
        if refresh_token is not None:
            row.refresh_token_enc = self._cipher.encrypt(refresh_token)
        if token_type is not None:
            row.token_type = token_type
        if scope is not None:
            row.scope = scope
        if expires_at is not None:
            row.expires_at = expires_at
        if extra is not None:
            row.extra_enc = self._cipher.encrypt(
                json.dumps(extra, separators=(",", ":"))
            )
        self._session.flush()
        return row

    def get_plaintext(
        self, *, tenant_id: UUID, integration_id: UUID
    ) -> dict[str, Any] | None:
        """Decrypt credentials for server-side provider use only."""
        row = self._session.scalar(
            select(IntegrationCredential).where(
                IntegrationCredential.tenant_id == tenant_id,
                IntegrationCredential.integration_id == integration_id,
            )
        )
        if row is None:
            return None
        extra: dict[str, Any] = {}
        if row.extra_enc:
            try:
                parsed = json.loads(self._cipher.decrypt(row.extra_enc))
                if isinstance(parsed, dict):
                    extra = parsed
            except Exception:
                extra = {}
        return {
            "access_token": (
                self._cipher.decrypt(row.access_token_enc)
                if row.access_token_enc
                else None
            ),
            "refresh_token": (
                self._cipher.decrypt(row.refresh_token_enc)
                if row.refresh_token_enc
                else None
            ),
            "token_type": row.token_type,
            "scope": row.scope,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
            "extra": extra,
            "has_access_token": bool(row.access_token_enc),
            "has_refresh_token": bool(row.refresh_token_enc),
        }

    def delete(self, *, tenant_id: UUID, integration_id: UUID) -> None:
        row = self._session.scalar(
            select(IntegrationCredential).where(
                IntegrationCredential.tenant_id == tenant_id,
                IntegrationCredential.integration_id == integration_id,
            )
        )
        if row is not None:
            self._session.delete(row)
            self._session.flush()

    def public_meta(
        self, *, tenant_id: UUID, integration_id: UUID
    ) -> dict[str, Any] | None:
        """Safe metadata for API responses (no secrets)."""
        row = self._session.scalar(
            select(IntegrationCredential).where(
                IntegrationCredential.tenant_id == tenant_id,
                IntegrationCredential.integration_id == integration_id,
            )
        )
        if row is None:
            return None
        return {
            "has_access_token": bool(row.access_token_enc),
            "has_refresh_token": bool(row.refresh_token_enc),
            "token_type": row.token_type,
            "scope": row.scope,
            "expires_at": row.expires_at.isoformat() if row.expires_at else None,
        }
