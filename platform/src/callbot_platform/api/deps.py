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
from callbot_platform.security.rate_limit import (
    RateLimitExceeded,
    SlidingWindowRateLimiter,
)
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
from callbot_platform.tenancy import (
    TenantContext,
    TenantSource,
    set_tenant_context,
)

_API_KEY_LIMITER = SlidingWindowRateLimiter(max_requests=120, window_sec=60.0)


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


@dataclass(frozen=True, slots=True)
class ApiKeyPrincipal:
    key_id: UUID
    tenant_id: UUID
    scopes: frozenset[str]
    name: str

    def require_scope(self, scope: str) -> None:
        if scope not in self.scopes:
            raise HTTPException(
                status_code=403,
                detail={"code": "missing_scope", "message": f"Missing scope: {scope}"},
            )


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
        raise HTTPException(
            status_code=500, detail="INTERNAL_SERVICE_TOKEN not configured"
        )
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
    current = CurrentUser(
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
    set_tenant_context(
        TenantContext(tenant_id=current.tenant_id, source=TenantSource.SESSION)
    )
    return current


def require_api_key(
    request: Request,
    session: Session = Depends(db_dep),
) -> ApiKeyPrincipal:
    """Authenticate public /v1 requests with Authorization: Bearer cbk_…."""
    from callbot_platform.api_keys import ApiKeyRepository

    auth = request.headers.get("Authorization") or ""
    if not auth.lower().startswith("bearer "):
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Bearer API key required"},
        )
    token = auth[7:].strip()
    row = ApiKeyRepository(session).authenticate(token)
    if row is None:
        raise HTTPException(
            status_code=401,
            detail={"code": "unauthorized", "message": "Invalid API key"},
        )
    principal = ApiKeyPrincipal(
        key_id=row.id,
        tenant_id=row.tenant_id,
        scopes=frozenset(row.scopes or []),
        name=row.name,
    )
    set_tenant_context(
        TenantContext(tenant_id=principal.tenant_id, source=TenantSource.API_KEY)
    )
    try:
        _API_KEY_LIMITER.check(str(row.id))
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={"code": "rate_limited", "message": "Too many API requests"},
            headers={"Retry-After": str(int(exc.retry_after_sec) + 1)},
        ) from exc
    return principal


def require_ops_roles(*roles: str) -> Callable[..., CurrentUser]:
    """Deprecated legacy JWT-role gate.

    Task 1.3.1: do not use for authorization. Prefer
    ``require_permission`` / ``require_entitled_permission``.
    Kept only so accidental imports fail loudly at review time via audit docs.
    """
    allowed = frozenset(roles)

    def _dep(user: CurrentUser = Depends(require_tenant_user)) -> CurrentUser:  # noqa: B008
        if user.role not in allowed:
            raise HTTPException(status_code=403, detail="Insufficient role")
        return user

    return _dep


def require_permission(permission_key: str) -> Callable[..., CurrentUser]:
    """Session-scoped permission check (RBAC). Entitlement not required here."""

    def _dep(
        user: CurrentUser = Depends(require_tenant_user),  # noqa: B008
        session: Session = Depends(db_dep),  # noqa: B008
    ) -> CurrentUser:
        from callbot_platform.rbac.errors import RbacError
        from callbot_platform.rbac.service import AuthorizationService

        try:
            AuthorizationService(session).require_permission(
                user.tenant_id, user.user_id, permission_key
            )
        except RbacError as exc:
            raise HTTPException(
                status_code=403,
                detail={"code": exc.code, "message": str(exc)},
            ) from exc
        return user

    return _dep


def require_entitled_permission(permission_key: str) -> Callable[..., CurrentUser]:
    perm_dep = require_permission(permission_key)

    def _dep(
        user: CurrentUser = Depends(perm_dep),  # noqa: B008
        session: Session = Depends(db_dep),  # noqa: B008
        settings: Settings = Depends(settings_dep),  # noqa: B008
    ) -> CurrentUser:
        from callbot_platform.billing.service import BillingService

        if not BillingService(session, settings).tenant_is_entitled(user.tenant_id):
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "subscription_required",
                    "message": "An active subscription is required. Complete billing setup.",
                },
            )
        return user

    return _dep


def require_entitled_ops_roles(*roles: str) -> Callable[..., CurrentUser]:
    """Deprecated. Prefer ``require_entitled_permission``.

    Legacy tenants with no subscription row remain entitled when tenant.status is active.
    """
    role_dep = require_ops_roles(*roles)

    def _dep(
        user: CurrentUser = Depends(role_dep),  # noqa: B008
        session: Session = Depends(db_dep),  # noqa: B008
        settings: Settings = Depends(settings_dep),  # noqa: B008
    ) -> CurrentUser:
        from callbot_platform.billing.service import BillingService

        if not BillingService(session, settings).tenant_is_entitled(user.tenant_id):
            raise HTTPException(
                status_code=402,
                detail={
                    "code": "subscription_required",
                    "message": "An active subscription is required. Complete billing setup.",
                },
            )
        return user

    return _dep


def require_entitled_tenant_user(
    user: CurrentUser = Depends(require_tenant_user),
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> CurrentUser:
    """Any authenticated tenant user with an entitled subscription."""
    from callbot_platform.billing.service import BillingService

    if not BillingService(session, settings).tenant_is_entitled(user.tenant_id):
        raise HTTPException(
            status_code=402,
            detail={
                "code": "subscription_required",
                "message": "An active subscription is required. Complete billing setup.",
            },
        )
    return user


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
