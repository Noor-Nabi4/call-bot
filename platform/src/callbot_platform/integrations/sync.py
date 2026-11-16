"""Generic sync engine — pagination, cursor, idempotent mapping hooks."""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models.integrations import (
    IntegrationConnection,
    IntegrationExternalMapping,
    IntegrationSyncRun,
)
from callbot_platform.integrations.constants import (
    IntegrationStatus,
    SyncRunStatus,
)
from callbot_platform.integrations.credentials import IntegrationCredentialStore
from callbot_platform.integrations.errors import IntegrationError
from callbot_platform.integrations.registry import get_provider
from callbot_platform.security.crypto import CredentialCipher

logger = logging.getLogger(__name__)


class SyncEngine:
    def __init__(self, session: Session, cipher: CredentialCipher) -> None:
        self._session = session
        self._creds = IntegrationCredentialStore(session, cipher)

    def run(
        self,
        *,
        tenant_id: UUID,
        integration_id: UUID,
        sync_run_id: UUID,
        max_pages: int = 50,
    ) -> dict[str, Any]:
        conn = self._session.scalar(
            select(IntegrationConnection).where(
                IntegrationConnection.tenant_id == tenant_id,
                IntegrationConnection.id == integration_id,
            )
        )
        if conn is None:
            raise IntegrationError("NOT_FOUND", "Integration not found")

        run = self._session.scalar(
            select(IntegrationSyncRun).where(
                IntegrationSyncRun.tenant_id == tenant_id,
                IntegrationSyncRun.id == sync_run_id,
            )
        )
        if run is None:
            raise IntegrationError("NOT_FOUND", "Sync run not found")

        run.status = SyncRunStatus.RUNNING.value
        run.started_at = datetime.now(UTC)
        conn.status = IntegrationStatus.SYNCING.value
        self._session.flush()

        provider = get_provider(conn.provider)
        credentials = self._creds.get_plaintext(
            tenant_id=tenant_id, integration_id=integration_id
        )
        cursor = conn.sync_cursor
        pages = 0
        processed = created = updated = skipped = 0

        try:
            while pages < max_pages:
                page = provider.sync_page(
                    tenant_id=tenant_id,
                    credentials=credentials,
                    cursor=cursor,
                    direction=conn.sync_direction,
                )
                pages += 1
                for item in page.items:
                    external_id = getattr(item, "external_id", None) or (
                        item.get("external_id") if isinstance(item, dict) else None
                    )
                    if not external_id:
                        skipped += 1
                        continue
                    entity_type = (
                        type(item).__name__
                        if not isinstance(item, dict)
                        else (item.get("entity_type") or "record")
                    )
                    existing = self._session.scalar(
                        select(IntegrationExternalMapping).where(
                            IntegrationExternalMapping.tenant_id == tenant_id,
                            IntegrationExternalMapping.integration_id == integration_id,
                            IntegrationExternalMapping.entity_type == str(entity_type),
                            IntegrationExternalMapping.external_id == str(external_id),
                        )
                    )
                    processed += 1
                    if existing is None:
                        # Mapping placeholder until provider-specific domain upsert links
                        # a real CRM entity. External ID uniqueness prevents duplicates.
                        self._session.add(
                            IntegrationExternalMapping(
                                tenant_id=tenant_id,
                                integration_id=integration_id,
                                entity_type=str(entity_type),
                                internal_id=uuid4(),
                                external_id=str(external_id),
                                last_synced_at=datetime.now(UTC),
                            )
                        )
                        created += 1
                    else:
                        existing.last_synced_at = datetime.now(UTC)
                        updated += 1
                cursor = page.next_cursor
                if page.done or not page.next_cursor:
                    break

            conn.sync_cursor = cursor
            conn.last_sync_at = datetime.now(UTC)
            conn.last_success_at = datetime.now(UTC)
            conn.status = IntegrationStatus.SYNCED.value
            conn.last_error_code = None
            conn.last_error_message = None
            run.status = SyncRunStatus.SUCCEEDED.value
            run.records_processed = processed
            run.records_created = created
            run.records_updated = updated
            run.records_skipped = skipped
            run.finished_at = datetime.now(UTC)
            run.stats_json = {"pages": pages}
            self._session.flush()
            logger.info(
                "integration_sync_succeeded tenant_id=%s integration_id=%s "
                "provider=%s pages=%s processed=%s created=%s updated=%s skipped=%s",
                tenant_id,
                integration_id,
                conn.provider,
                pages,
                processed,
                created,
                updated,
                skipped,
            )
            return {
                "status": run.status,
                "processed": processed,
                "created": created,
                "updated": updated,
                "skipped": skipped,
                "pages": pages,
            }
        except IntegrationError as exc:
            conn.status = (
                IntegrationStatus.REAUTH_REQUIRED.value
                if exc.code in {"AUTH_EXPIRED", "AUTH_REVOKED"}
                else IntegrationStatus.ERROR.value
            )
            conn.last_error_at = datetime.now(UTC)
            conn.last_error_code = exc.code
            conn.last_error_message = exc.message[:500]
            run.status = SyncRunStatus.FAILED.value
            run.error_code = exc.code
            run.error_message = exc.message[:500]
            run.finished_at = datetime.now(UTC)
            self._session.flush()
            if exc.retryable:
                raise
            return {
                "status": run.status,
                "error_code": exc.code,
                "error_message": exc.message,
            }
