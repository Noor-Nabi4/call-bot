"""Public and authenticated SaaS billing routes (platform Stripe account)."""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_ops_roles,
    settings_dep,
)
from callbot_platform.billing.errors import BillingError
from callbot_platform.billing.service import BillingService
from callbot_platform.config import Settings
from callbot_platform.security.session import ROLE_ADMIN

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])


class CheckoutBody(BaseModel):
    model_config = {"extra": "forbid"}

    plan_key: str | None = Field(default=None, max_length=32)


def _billing_http(exc: Exception) -> HTTPException:
    if isinstance(exc, BillingError):
        status = 400
        if exc.code in {"subscription_not_found", "tenant_not_found"}:
            status = 404
        if exc.code == "stripe_not_configured":
            status = 503
        if exc.code == "invalid_signature":
            status = 400
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


@router.get("/plans")
def list_plans(
    enrich: bool = False,
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    service = BillingService(session, settings)
    return service.pricing_catalog(enrich_from_stripe=enrich)


@router.get("/subscription")
def get_subscription(
    user: CurrentUser = Depends(require_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    service = BillingService(session, settings)
    sub = service.get_subscription(user.tenant_id)
    if sub is None:
        return {"subscription": None}
    return {"subscription": sub}


@router.get("/usage")
def get_usage(
    user: CurrentUser = Depends(require_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    service = BillingService(session, settings)
    return {"usage": service.get_usage(user.tenant_id)}


@router.post("/checkout")
def create_checkout(
    body: CheckoutBody,
    user: CurrentUser = Depends(require_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    try:
        from uuid import UUID

        from callbot_platform.async_jobs.runner import run_async_job
        from callbot_platform.db import get_session_factory

        queued = BillingService(session, settings).create_checkout_for_tenant(
            tenant_id=user.tenant_id,
            plan_key=body.plan_key,
        )
        session.commit()
        job_id = queued.get("job_id")
        if job_id:
            run_async_job(get_session_factory(), UUID(str(job_id)), settings=settings)
        info = BillingService(session, settings).get_signup_checkout(user.tenant_id)
        return {
            "checkout_url": info.get("checkout_url") or "",
            "job_id": str(job_id) if job_id else "",
            "provisioning": str(info.get("provisioning_status") or "ready"),
        }
    except Exception as exc:
        session.rollback()
        raise _billing_http(exc) from exc


@router.post("/portal")
def create_portal(
    user: CurrentUser = Depends(require_ops_roles(ROLE_ADMIN)),
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> dict[str, str]:
    try:
        url = BillingService(session, settings).create_portal_session(
            tenant_id=user.tenant_id
        )
        return {"portal_url": url}
    except Exception as exc:
        raise _billing_http(exc) from exc


@router.post("/webhooks/stripe")
async def stripe_webhook(
    request: Request,
    session: Session = Depends(db_dep),
    settings: Settings = Depends(settings_dep),
) -> dict[str, Any]:
    payload = await request.body()
    signature = request.headers.get("Stripe-Signature")
    service = BillingService(session, settings)
    try:
        event = service.construct_webhook_event(payload, signature)
        result = service.handle_webhook_event(event)
        session.commit()
        return result
    except BillingError as exc:
        session.rollback()
        raise _billing_http(exc) from exc
    except Exception as exc:
        session.rollback()
        logger.exception("Stripe webhook processing failed")
        raise HTTPException(
            status_code=500,
            detail={"code": "webhook_failed", "message": "Webhook processing failed"},
        ) from exc
