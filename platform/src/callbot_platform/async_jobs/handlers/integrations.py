"""Async job handlers for Phase 28 integration sync and OAuth refresh."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy.orm import Session

from callbot_platform.config import Settings
from callbot_platform.db.models.async_job import AsyncJob
from callbot_platform.integrations.service import IntegrationService
from callbot_platform.integrations.sync import SyncEngine
from callbot_platform.security.crypto import CredentialCipher


class IntegrationJobHandler:
    def __init__(self, *, settings: Settings) -> None:
        self._settings = settings

    def handle_sync(self, session: Session, job: AsyncJob) -> dict:
        payload = job.payload or {}
        integration_id = UUID(str(payload["integration_id"]))
        sync_run_id = UUID(str(payload["sync_run_id"]))
        cipher = CredentialCipher(self._settings.credentials_encryption_key)
        engine = SyncEngine(session, cipher)
        return engine.run(
            tenant_id=job.tenant_id,
            integration_id=integration_id,
            sync_run_id=sync_run_id,
        )

    def handle_oauth_refresh(self, session: Session, job: AsyncJob) -> dict:
        payload = job.payload or {}
        integration_id = UUID(str(payload["integration_id"]))
        cipher = CredentialCipher(self._settings.credentials_encryption_key)
        svc = IntegrationService(session, settings=self._settings, cipher=cipher)
        result = svc.refresh_credentials(
            job.tenant_id,
            integration_id,
            actor=str(payload.get("actor") or "system"),
        )
        return {
            "integration_id": str(integration_id),
            "status": result.get("status"),
            "has_access_token": bool(
                (result.get("credentials") or {}).get("has_access_token")
            ),
        }
