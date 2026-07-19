"""FastAPI dependency wiring."""

from __future__ import annotations

from collections.abc import Callable, Generator
from dataclasses import dataclass
from typing import Any
from uuid import UUID

import jwt
from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from callbot_platform.auth.repos import AuthRepository
from callbot_platform.config import Settings, get_settings
from callbot_platform.db import get_db
from callbot_platform.security.crypto import CredentialCipher
from callbot_platform.security.metadata import MetadataSigner
from callbot_platform.security.session import decode_session_token
from callbot_platform.telephony.adapters.livekit_sip import LiveKitSipService
from callbot_platform.telephony.adapters.twilio_adapter import (
    TwilioNumberInventoryService,
    TwilioNumberProvisioningService,
    TwilioSipTrunkService,
)
from callbot_platform.telephony.services.connect_existing import ConnectExistingService
from callbot_platform.telephony.services.purchase import PlatformPurchaseService
from callbot_platform.telephony.services.resolver import DbTenantDidResolver
from callbot_platform.telephony.services.verification import DbNumberVerificationService


@dataclass(frozen=True, slots=True)
class CurrentUser:
    user_id: UUID
    tenant_id: UUID
    role: str
    email: str
    name: str
    tenant_slug: str
    tenant_name: str
    technician_id: UUID | None = None

    def as_dict(self) -> dict[str, Any]:
        return {
            "id": str(self.user_id),
            "tenant_id": str(self.tenant_id),
            "tenant_slug": self.tenant_slug,
            "tenant_name": self.tenant_name,
            "email": self.email,
            "name": self.name,
            "role": self.role,
            "technician_id": str(self.technician_id) if self.technician_id else None,
        }


def settings_dep() -> Settings:
    return get_settings()


def db_dep() -> Generator[Session, None, None]:
    yield from get_db()


def require_internal_token(
    settings: Settings = Depends(settings_dep),
    x_internal_token: str | None = Header(default=None, alias="X-Internal-Token"),
) -> None:
    expected = settings.internal_service_token
    if not expected:
        raise HTTPException(status_code=500, detail="INTERNAL_SERVICE_TOKEN not configured")
    if not x_internal_token or x_internal_token != expected:
        raise HTTPException(status_code=401, detail="Invalid internal service token")


def require_tenant_user(
    request: Request,
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> CurrentUser:
    token = request.cookies.get(settings.session_cookie_name)
    if not token:
        auth = request.headers.get("Authorization") or ""
        if auth.lower().startswith("bearer "):
            token = auth[7:].strip()
    if not token:
        raise HTTPException(status_code=401, detail="Not authenticated")
    try:
        payload = decode_session_token(token, settings=settings)
    except (jwt.PyJWTError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc
    try:
        user_id = UUID(str(payload["sub"]))
        tenant_id = UUID(str(payload["tenant_id"]))
    except (KeyError, ValueError) as exc:
        raise HTTPException(status_code=401, detail="Invalid session") from exc
    user = AuthRepository(session).get_user(tenant_id, user_id)
    if user is None:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return CurrentUser(
        user_id=user_id,
        tenant_id=tenant_id,
        role=user["role"],
        email=user["email"],
        name=user["name"],
        tenant_slug=user["tenant_slug"],
        tenant_name=user["tenant_name"],
        technician_id=(
            UUID(user["technician_id"]) if user.get("technician_id") else None
        ),
    )


def require_ops_roles(*roles: str) -> Callable[..., CurrentUser]:
    allowed = frozenset(roles)

    def _dep(user: CurrentUser = Depends(require_tenant_user)) -> CurrentUser:
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return _dep


def signer_dep(settings: Settings = Depends(settings_dep)) -> MetadataSigner:
    try:
        return MetadataSigner(settings.metadata_hmac_secret)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def cipher_dep(settings: Settings = Depends(settings_dep)) -> CredentialCipher:
    try:
        return CredentialCipher(settings.credentials_encryption_key)
    except ValueError as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def livekit_dep(settings: Settings = Depends(settings_dep)) -> LiveKitSipService:
    try:
        return LiveKitSipService(
            url=settings.livekit_url,
            api_key=settings.livekit_api_key,
            api_secret=settings.livekit_api_secret,
        )
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc)) from exc


def connect_service(
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
    livekit: LiveKitSipService = Depends(livekit_dep),
    signer: MetadataSigner = Depends(signer_dep),
) -> ConnectExistingService:
    return ConnectExistingService(session, settings, livekit, signer)


def verification_service(
    session: Session = Depends(db_dep),
) -> DbNumberVerificationService:
    return DbNumberVerificationService(session)


def purchase_service(
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
    cipher: CredentialCipher = Depends(cipher_dep),
    signer: MetadataSigner = Depends(signer_dep),
    livekit: LiveKitSipService = Depends(livekit_dep),
) -> PlatformPurchaseService:
    return PlatformPurchaseService(
        session,
        settings,
        cipher=cipher,
        signer=signer,
        inventory=TwilioNumberInventoryService(),
        provisioning=TwilioNumberProvisioningService(),
        twilio_sip=TwilioSipTrunkService(),
        livekit=livekit,
    )


def resolver_service(
    session: Session = Depends(db_dep),
    signer: MetadataSigner = Depends(signer_dep),
) -> DbTenantDidResolver:
    return DbTenantDidResolver(session, signer)
