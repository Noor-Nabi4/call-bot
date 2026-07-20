"""Fail-closed tenant DID resolver."""

from __future__ import annotations

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from callbot_platform.crm.repos.agent_profile_repo import AgentProfileRepository
from callbot_platform.db.models import TenantPhoneNumber
from callbot_platform.domain.enums import ConnectionStatus, VerificationStatus
from callbot_platform.domain.phone import PhoneNumberError, normalize_e164
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.telephony.interfaces import ResolveRequest, ResolveResult


class TenantResolveError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class DbTenantDidResolver:
    def __init__(self, session: Session, signer: MetadataSigner) -> None:
        self._session = session
        self._signer = signer
        self._profiles = AgentProfileRepository(session)

    def resolve(self, request: ResolveRequest) -> ResolveResult:
        meta = self._signer.verify_and_parse(request.job_metadata_raw)
        meta_tenant: UUID | None = None
        meta_did: str | None = None
        meta_profile: UUID | None = None
        if meta is not None:
            raw_tenant = meta.get("tenant_id")
            if raw_tenant:
                try:
                    meta_tenant = UUID(str(raw_tenant))
                except ValueError as exc:
                    raise TenantResolveError(
                        "invalid_metadata", "Invalid tenant_id in signed metadata"
                    ) from exc
            raw_did = meta.get("did")
            if raw_did:
                try:
                    meta_did = normalize_e164(str(raw_did))
                except PhoneNumberError as exc:
                    raise TenantResolveError(
                        "invalid_metadata", "Invalid did in signed metadata"
                    ) from exc
            raw_profile = meta.get("agent_profile_id")
            if raw_profile:
                try:
                    meta_profile = UUID(str(raw_profile))
                except ValueError as exc:
                    raise TenantResolveError(
                        "invalid_metadata",
                        "Invalid agent_profile_id in signed metadata",
                    ) from exc

        called: str | None = None
        if request.called_number:
            try:
                called = normalize_e164(request.called_number)
            except PhoneNumberError as exc:
                raise TenantResolveError("invalid_did", str(exc)) from exc

        if meta_did and called and meta_did != called:
            raise TenantResolveError(
                "metadata_conflict",
                "Signed metadata DID does not match called number",
            )

        lookup_did = called or meta_did
        did_row: TenantPhoneNumber | None = None
        if lookup_did:
            did_row = self._active_by_did(lookup_did)

        trunk_rows: list[TenantPhoneNumber] = []
        if request.livekit_inbound_trunk_id:
            trunk_rows = self._active_by_trunk(request.livekit_inbound_trunk_id)
            if len(trunk_rows) > 1:
                raise TenantResolveError(
                    "ambiguous_trunk",
                    "Multiple tenants match LiveKit inbound trunk",
                )

        # Priority 1: signed metadata
        if meta_tenant is not None:
            if did_row and did_row.tenant_id != meta_tenant:
                raise TenantResolveError(
                    "metadata_conflict",
                    "Signed metadata tenant_id conflicts with DID mapping",
                )
            if trunk_rows and trunk_rows[0].tenant_id != meta_tenant:
                raise TenantResolveError(
                    "metadata_conflict",
                    "Signed metadata tenant_id conflicts with trunk mapping",
                )
            phone = did_row
            if phone is None and lookup_did is None and not request.is_sip:
                return self._result(
                    tenant_id=meta_tenant,
                    phone=None,
                    source="signed_metadata",
                    explicit_profile_id=meta_profile,
                    require_profile=False,
                )
            if phone is None and lookup_did and request.is_sip:
                raise TenantResolveError(
                    "did_inactive",
                    "Called DID is not active and verified",
                )
            if phone is not None:
                return self._result(
                    tenant_id=meta_tenant,
                    phone=phone,
                    source="signed_metadata",
                    explicit_profile_id=meta_profile,
                    require_profile=request.is_sip,
                )
            if not request.is_sip:
                return self._result(
                    tenant_id=meta_tenant,
                    phone=None,
                    source="signed_metadata",
                    explicit_profile_id=meta_profile,
                    require_profile=False,
                )

        # Priority 2: exact called DID
        if lookup_did:
            if did_row is None:
                any_row = self._session.scalar(
                    select(TenantPhoneNumber).where(
                        TenantPhoneNumber.e164 == lookup_did
                    )
                )
                if any_row is None:
                    raise TenantResolveError(
                        "unknown_did", f"Unknown DID: {lookup_did}"
                    )
                if any_row.connection_status != ConnectionStatus.ACTIVE.value:
                    raise TenantResolveError(
                        "did_inactive",
                        f"DID is not active (status={any_row.connection_status})",
                    )
                if any_row.verification_status != VerificationStatus.VERIFIED.value:
                    raise TenantResolveError(
                        "did_unverified",
                        f"DID is not verified (status={any_row.verification_status})",
                    )
                raise TenantResolveError("unknown_did", f"Unknown DID: {lookup_did}")
            return self._result(
                tenant_id=did_row.tenant_id,
                phone=did_row,
                source="did_mapping",
                explicit_profile_id=None,
                require_profile=request.is_sip,
            )

        # Priority 3: LiveKit trunk metadata / id
        if trunk_rows:
            row = trunk_rows[0]
            return self._result(
                tenant_id=row.tenant_id,
                phone=row,
                source="livekit_trunk",
                explicit_profile_id=None,
                require_profile=request.is_sip,
            )

        raise TenantResolveError("unresolved", "Unable to resolve tenant for call")

    def _result(
        self,
        *,
        tenant_id: UUID,
        phone: TenantPhoneNumber | None,
        source: str,
        explicit_profile_id: UUID | None,
        require_profile: bool,
    ) -> ResolveResult:
        profile_id = self._profiles.resolve_profile_id(
            tenant_id,
            explicit_profile_id=explicit_profile_id,
            phone_profile_id=phone.agent_profile_id if phone else None,
        )
        if require_profile and profile_id is None:
            raise TenantResolveError(
                "agent_profile_missing",
                "No active agent profile assigned for this call",
            )
        return ResolveResult(
            tenant_id=tenant_id,
            phone_number_id=phone.id if phone else None,
            e164=phone.e164 if phone else None,
            source=source,
            livekit_inbound_trunk_id=phone.livekit_inbound_trunk_id if phone else None,
            livekit_dispatch_rule_id=phone.livekit_dispatch_rule_id if phone else None,
            agent_profile_id=profile_id,
        )

    def _active_by_did(self, e164: str) -> TenantPhoneNumber | None:
        rows = list(
            self._session.scalars(
                select(TenantPhoneNumber).where(TenantPhoneNumber.e164 == e164)
            )
        )
        if len(rows) > 1:
            raise TenantResolveError(
                "ambiguous_did", "Multiple tenants match the same DID"
            )
        if not rows:
            return None
        row = rows[0]
        if row.connection_status != ConnectionStatus.ACTIVE.value:
            return None
        if row.verification_status != VerificationStatus.VERIFIED.value:
            return None
        return row

    def _active_by_trunk(self, trunk_id: str) -> list[TenantPhoneNumber]:
        rows = list(
            self._session.scalars(
                select(TenantPhoneNumber).where(
                    TenantPhoneNumber.livekit_inbound_trunk_id == trunk_id,
                    TenantPhoneNumber.connection_status
                    == ConnectionStatus.ACTIVE.value,
                    TenantPhoneNumber.verification_status
                    == VerificationStatus.VERIFIED.value,
                )
            )
        )
        return rows
