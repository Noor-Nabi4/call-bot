"""FastAPI dependency wiring."""

from __future__ import annotations

from collections.abc import Generator

from fastapi import Depends, Header, HTTPException
from sqlalchemy.orm import Session

from callbot_platform.config import Settings, get_settings
from callbot_platform.db import get_db
from callbot_platform.security.crypto import CredentialCipher
from callbot_platform.security.metadata import MetadataSigner
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
