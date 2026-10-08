"""Serialize communication templates for API responses."""

from __future__ import annotations

from typing import Any

from callbot_platform.db.models.communication_templates import (
    CommunicationTemplate,
    CommunicationTemplateVersion,
)


def serialize_version(row: CommunicationTemplateVersion) -> dict[str, Any]:
    return {
        "id": str(row.id),
        "template_id": str(row.template_id),
        "version": row.version,
        "subject_template": row.subject_template,
        "body_template": row.body_template,
        "status": row.status,
        "created_by": row.created_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def serialize_template(
    row: CommunicationTemplate,
    *,
    active: CommunicationTemplateVersion | None = None,
    versions: list[CommunicationTemplateVersion] | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "id": str(row.id),
        "tenant_id": str(row.tenant_id),
        "channel": row.channel,
        "template_key": row.template_key,
        "name": row.name,
        "description": row.description,
        "status": row.status,
        "active_version": row.active_version,
        "created_by": row.created_by,
        "updated_by": row.updated_by,
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }
    if active is not None:
        data["subject_template"] = active.subject_template
        data["body_template"] = active.body_template
        data["version"] = active.version
    if versions is not None:
        data["versions"] = [serialize_version(v) for v in versions]
    return data
