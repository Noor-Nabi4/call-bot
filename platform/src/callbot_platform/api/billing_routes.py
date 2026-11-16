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
    require_permission,
    settings_dep,
)
from callbot_platform.billing.errors import BillingError
from callbot_platform.billing.service import BillingService
from callbot_platform.config import Settings

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

# Billing must remain reachable so signup checkout can finish before onboarding.
_require_billing_read = require_permission(
    "billing.read", allow_incomplete_onboarding=True
)
_require_billing_manage = require_permission(
    "billing.manage", allow_incomplete_onboarding=True
)


class CheckoutBody(BaseModel):
    model_config = {"extra": "forbid"}

    plan_key: str | None = Field(default=None, max_length=32)


class TopupBody(BaseModel):
    model_config = {"extra": "forbid"}

    amount_cents: int = Field(..., ge=500, le=500_000)


class SubscribeBody(BaseModel):
    model_config = {"extra": "forbid"}

    plan_key: str | None = Field(default=None, max_length=32)


class ChangePlanBody(BaseModel):
    model_config = {"extra": "forbid"}

    plan_key: str = Field(..., min_length=2, max_length=32)


def _billing_http(exc: Exception) -> HTTPException:
    from callbot_platform.billing.wallet.service import WalletError

    if isinstance(exc, (BillingError, WalletError)):
        status = 400
        if exc.code in {"subscription_not_found", "tenant_not_found"}:
            status = 404
        if exc.code == "stripe_not_configured":
            status = 503
        if exc.code == "invalid_signature":
            status = 400
        if exc.code == "insufficient_funds":
            status = 402
        return HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        )
    return HTTPException(
        status_code=500, detail={"code": "internal", "message": str(exc)}
    )


@router.get("/plans")
def list_plans(
    enrich: bool = False,
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    service = BillingService(session, settings)
    return service.pricing_catalog(enrich_from_stripe=enrich)


@router.get("/subscription")
def get_subscription(
    user: CurrentUser = Depends(_require_billing_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    service = BillingService(session, settings)
    sub = service.get_subscription(user.tenant_id)
    if sub is None:
        return {"subscription": None}
    return {"subscription": sub}


@router.get("/usage")
def get_usage(
    user: CurrentUser = Depends(_require_billing_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    service = BillingService(session, settings)
    return {"usage": service.get_usage(user.tenant_id)}


@router.get("/wallet")
def get_wallet(
    user: CurrentUser = Depends(_require_billing_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.billing.wallet.service import WalletService

    return {"wallet": WalletService(session).get_balance(user.tenant_id)}


@router.get("/wallet/transactions")
def list_wallet_transactions(
    limit: int = 50,
    offset: int = 0,
    user: CurrentUser = Depends(_require_billing_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.billing.wallet.service import WalletService

    rows = WalletService(session).list_transactions(
        user.tenant_id, limit=limit, offset=offset
    )
    return {"transactions": rows}


@router.get("/wallet/topup-presets")
def wallet_topup_presets(
    user: CurrentUser = Depends(_require_billing_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.billing.wallet.topup_service import WalletTopupService

    _ = user
    return WalletTopupService(session, settings).presets()


@router.post("/wallet/topups")
def create_wallet_topup(
    body: TopupBody,
    user: CurrentUser = Depends(_require_billing_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        from callbot_platform.billing.wallet.topup_service import WalletTopupService

        result = WalletTopupService(session, settings).create_topup_checkout(
            tenant_id=user.tenant_id,
            amount_cents=body.amount_cents,
            auto_activate_plan=True,
        )
        session.commit()
        return result
    except Exception as exc:
        session.rollback()
        raise _billing_http(exc) from exc


@router.post("/subscribe")
def subscribe_from_wallet(
    body: SubscribeBody,
    user: CurrentUser = Depends(_require_billing_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    _ = settings
    try:
        from callbot_platform.billing.subscription_wallet import (
            SubscriptionWalletService,
        )

        sub = SubscriptionWalletService(session).activate_from_wallet(
            user.tenant_id, plan_key=body.plan_key
        )
        session.commit()
        return {"subscription": sub}
    except Exception as exc:
        session.rollback()
        raise _billing_http(exc) from exc


@router.post("/change-plan")
def change_plan(
    body: ChangePlanBody,
    user: CurrentUser = Depends(_require_billing_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    _ = settings
    try:
        from callbot_platform.billing.subscription_wallet import (
            SubscriptionWalletService,
        )

        sub = SubscriptionWalletService(session).change_plan(
            user.tenant_id, plan_key=body.plan_key
        )
        session.commit()
        return {"subscription": sub}
    except Exception as exc:
        session.rollback()
        raise _billing_http(exc) from exc


@router.get("/summary")
def billing_summary(
    user: CurrentUser = Depends(_require_billing_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.billing.wallet.service import WalletService

    service = BillingService(session, settings)
    return {
        "subscription": service.get_subscription(user.tenant_id),
        "usage": service.get_usage(user.tenant_id),
        "wallet": WalletService(session).get_balance(user.tenant_id),
    }


@router.post("/checkout")
def create_checkout(
    body: CheckoutBody,
    user: CurrentUser = Depends(_require_billing_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
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
    user: CurrentUser = Depends(_require_billing_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
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
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
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
