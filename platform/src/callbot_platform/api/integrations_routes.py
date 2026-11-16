"""Admin APIs for Phase 28 Integrations."""

from __future__ import annotations

from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    CurrentUser,
    cipher_dep,
    db_dep,
    require_entitled_permission,
    settings_dep,
)
from callbot_platform.config import Settings
from callbot_platform.integrations.errors import IntegrationError
from callbot_platform.integrations.service import IntegrationService
from callbot_platform.security.crypto import CredentialCipher

router = APIRouter(prefix="/api/admin/integrations", tags=["integrations"])

_require_read = require_entitled_permission("integrations.read")
_require_connect = require_entitled_permission("integrations.connect")
_require_delete = require_entitled_permission("integrations.delete")
_require_sync = require_entitled_permission("integrations.sync")


def _svc(
    session: Session, settings: Settings, cipher: CredentialCipher
) -> IntegrationService:
    return IntegrationService(session, settings=settings, cipher=cipher)


def _http(exc: IntegrationError) -> HTTPException:
    status = 404 if exc.code == "NOT_FOUND" else 400
    if exc.code == "NOT_CONFIGURED":
        status = 503
    return HTTPException(
        status_code=status, detail={"code": exc.code, "message": exc.message}
    )


class ConnectBody(BaseModel):
    model_config = {"extra": "forbid"}
    redirect_uri: str = Field(min_length=8, max_length=512)
    shop: str | None = Field(
        default=None,
        max_length=255,
        description="Shopify shop domain (e.g. store.myshopify.com)",
    )


class ApiKeyConnectBody(BaseModel):
    model_config = {"extra": "forbid"}
    credentials: dict[str, str]
    display_name: str | None = Field(default=None, max_length=255)


class OAuthCallbackBody(BaseModel):
    model_config = {"extra": "forbid"}
    state: str = Field(min_length=8, max_length=128)
    code: str = Field(min_length=1, max_length=2048)


@router.get("/providers")
def list_providers(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    cipher: CredentialCipher = Depends(cipher_dep),  # noqa: B008
) -> dict[str, Any]:
    _ = user
    return {"providers": _svc(session, settings, cipher).list_providers()}


@router.get("")
def list_integrations(
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    cipher: CredentialCipher = Depends(cipher_dep),  # noqa: B008
) -> dict[str, Any]:
    return {
        "integrations": _svc(session, settings, cipher).list_connections(user.tenant_id)
    }


@router.get("/{integration_id}")
def get_integration(
    integration_id: UUID,
    user: CurrentUser = Depends(_require_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    cipher: CredentialCipher = Depends(cipher_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "integration": _svc(session, settings, cipher).get_connection(
                user.tenant_id, integration_id
            )
        }
    except IntegrationError as exc:
        raise _http(exc) from exc


@router.post("/{provider}/connect")
def start_connect(
    provider: str,
    body: ConnectBody,
    user: CurrentUser = Depends(_require_connect),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    cipher: CredentialCipher = Depends(cipher_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return _svc(session, settings, cipher).start_connect(
            user.tenant_id,
            user_id=user.user_id,
            provider=provider,
            redirect_uri=body.redirect_uri,
            actor=user.email,
            shop=body.shop,
        )
    except IntegrationError as exc:
        raise _http(exc) from exc


@router.post("/{provider}/callback")
def oauth_callback(
    provider: str,
    body: OAuthCallbackBody,
    user: CurrentUser = Depends(_require_connect),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    cipher: CredentialCipher = Depends(cipher_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "integration": _svc(session, settings, cipher).complete_oauth_callback(
                user.tenant_id,
                user_id=user.user_id,
                provider=provider,
                state=body.state,
                code=body.code,
                actor=user.email,
            )
        }
    except IntegrationError as exc:
        raise _http(exc) from exc


@router.post("/{provider}/api-key")
def connect_api_key(
    provider: str,
    body: ApiKeyConnectBody,
    user: CurrentUser = Depends(_require_connect),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    cipher: CredentialCipher = Depends(cipher_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "integration": _svc(session, settings, cipher).connect_api_key(
                user.tenant_id,
                provider=provider,
                credentials=body.credentials,
                actor=user.email,
                display_name=body.display_name,
            )
        }
    except IntegrationError as exc:
        raise _http(exc) from exc


@router.post("/{integration_id}/sync")
def sync_now(
    integration_id: UUID,
    user: CurrentUser = Depends(_require_sync),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    cipher: CredentialCipher = Depends(cipher_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return _svc(session, settings, cipher).enqueue_sync(
            user.tenant_id, integration_id, actor=user.email
        )
    except IntegrationError as exc:
        raise _http(exc) from exc


@router.delete("/{integration_id}")
def disconnect(
    integration_id: UUID,
    user: CurrentUser = Depends(_require_delete),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
    cipher: CredentialCipher = Depends(cipher_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        return {
            "integration": _svc(session, settings, cipher).disconnect(
                user.tenant_id, integration_id, actor=user.email
            )
        }
    except IntegrationError as exc:
        raise _http(exc) from exc
