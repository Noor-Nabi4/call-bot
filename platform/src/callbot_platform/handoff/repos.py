"""Tenant human-handoff configuration."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.db.models import TenantHandoffSettings
from callbot_platform.domain.phone import normalize_e164
from callbot_platform.telephony.audit import write_audit


class HandoffError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class HandoffRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def get(self, tenant_id: UUID) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantHandoffSettings).where(
                TenantHandoffSettings.tenant_id == tenant_id
            )
        )
        if row is None:
            return {
                "tenant_id": str(tenant_id),
                "enabled": False,
                "mode": "warm",
                "escalation_phone_e164": None,
                "sip_outbound_trunk_id": None,
            }
        return self._serialize(row)

    def upsert(
        self,
        tenant_id: UUID,
        *,
        enabled: bool | None = None,
        mode: str | None = None,
        escalation_phone_e164: str | None = None,
        sip_outbound_trunk_id: str | None = None,
        actor: str = "ops",
    ) -> dict[str, Any]:
        row = self._session.scalar(
            select(TenantHandoffSettings).where(
                TenantHandoffSettings.tenant_id == tenant_id
            )
        )
        if row is None:
            row = TenantHandoffSettings(
                tenant_id=tenant_id,
                enabled=False,
                mode="warm",
            )
            self._session.add(row)
        if enabled is not None:
            row.enabled = enabled
        if mode is not None:
            mode_n = mode.strip().lower()
            if mode_n not in {"warm", "cold"}:
                raise HandoffError("invalid_mode", "mode must be warm or cold")
            row.mode = mode_n
        if escalation_phone_e164 is not None:
            if escalation_phone_e164.strip():
                row.escalation_phone_e164 = normalize_e164(escalation_phone_e164)
            else:
                row.escalation_phone_e164 = None
        if sip_outbound_trunk_id is not None:
            row.sip_outbound_trunk_id = sip_outbound_trunk_id.strip() or None
        row.updated_at = datetime.now(UTC)
        self._session.flush()
        write_audit(
            self._session,
            tenant_id=tenant_id,
            actor=actor,
            action="handoff_settings_upserted",
            resource_ids={"tenant_id": str(tenant_id)},
        )
        return self._serialize(row)

    def _serialize(self, row: TenantHandoffSettings) -> dict[str, Any]:
        return {
            "tenant_id": str(row.tenant_id),
            "enabled": row.enabled,
            "mode": row.mode,
            "escalation_phone_e164": row.escalation_phone_e164,
            "sip_outbound_trunk_id": row.sip_outbound_trunk_id,
        }
