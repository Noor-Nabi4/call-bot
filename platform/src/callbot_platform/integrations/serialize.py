"""Safe API serialization — never include credentials."""

from __future__ import annotations

from typing import Any

from callbot_platform.db.models.integrations import (
    IntegrationConnection,
    IntegrationSyncRun,
)
from callbot_platform.integrations.catalog import get_descriptor
from callbot_platform.integrations.oauth import oauth_config_from_settings
from callbot_platform.integrations.protocols import ProviderDescriptor


def serialize_descriptor(d: ProviderDescriptor, *, settings: Any) -> dict[str, Any]:
    configured = True
    if d.oauth:
        configured = oauth_config_from_settings(d.key, settings) is not None
    # API-key providers (WooCommerce, ServiceTitan) are always available for tenant connect
    return {
        "key": d.key,
        "name": d.name,
        "category": d.category.value,
        "description": d.description,
        "capabilities": sorted(c.value for c in d.capabilities),
        "oauth": d.oauth,
        "default_sync_direction": d.default_sync_direction,
        "platform_configured": configured,
    }


def serialize_connection(
    row: IntegrationConnection,
    *,
    credential_meta: dict[str, Any] | None = None,
) -> dict[str, Any]:
    desc = get_descriptor(row.provider)
    return {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "category": row.category,
        "provider": row.provider,
        "provider_name": desc.name if desc else row.provider,
        "status": row.status,
        "display_name": row.display_name,
        "external_account_id": row.external_account_id,
        "sync_direction": row.sync_direction,
        "connected_at": row.connected_at.isoformat() if row.connected_at else None,
        "last_sync_at": row.last_sync_at.isoformat() if row.last_sync_at else None,
        "last_success_at": (
            row.last_success_at.isoformat() if row.last_success_at else None
        ),
        "last_error_at": row.last_error_at.isoformat() if row.last_error_at else None,
        "last_error_code": row.last_error_code,
        "last_error_message": row.last_error_message,
        "credentials": credential_meta,
        "capabilities": sorted(c.value for c in desc.capabilities) if desc else [],
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def serialize_sync_run(row: IntegrationSyncRun) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "integration_id": str(row.integration_id),
        "status": row.status,
        "direction": row.direction,
        "records_processed": row.records_processed,
        "records_created": row.records_created,
        "records_updated": row.records_updated,
        "records_skipped": row.records_skipped,
        "error_code": row.error_code,
        "error_message": row.error_message,
        "started_at": row.started_at.isoformat() if row.started_at else None,
        "finished_at": row.finished_at.isoformat() if row.finished_at else None,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }
