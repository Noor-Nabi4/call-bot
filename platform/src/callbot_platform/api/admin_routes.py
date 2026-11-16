"""Tenant admin APIs: CRM lists, metrics, users, retention, audit."""

from __future__ import annotations

from datetime import date
from typing import Any, Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from callbot_platform.admin.repos import AdminError, AdminRepository
from callbot_platform.analytics import AnalyticsRangeError, AnalyticsService
from callbot_platform.api.deps import (
    CurrentUser,
    db_dep,
    require_entitled_permission,
    require_platform_operator,
    settings_dep,
)
from callbot_platform.auth.repos import AuthError, AuthRepository
from callbot_platform.config import Settings
from callbot_platform.security.session import VALID_ROLES

router = APIRouter(prefix="/api/admin", tags=["admin"])

_require_customers_read = require_entitled_permission("customers.read")
_require_calls_read = require_entitled_permission("calls.read")
_require_calls_update = require_entitled_permission("calls.update")
_require_appointments_read = require_entitled_permission("appointments.read")
_require_analytics_read = require_entitled_permission("analytics.read")
_require_billing_read = require_entitled_permission("billing.read")
_require_handoff_read = require_entitled_permission("handoff.read")
_require_handoff_manage = require_entitled_permission("handoff.manage")
_require_team_read = require_entitled_permission("team.read")
_require_team_manage = require_entitled_permission("team.manage")
_require_org_update = require_entitled_permission("organization.update")
_require_org_read = require_entitled_permission("organization.read")
_require_ai_read = require_entitled_permission("ai.read")
_require_ai_configure = require_entitled_permission("ai.configure")


class InviteUserBody(BaseModel):
    email: str
    password: str = Field(min_length=8)
    name: str
    role: str
    phone: str | None = None


class UpdateUserBody(BaseModel):
    model_config = {"extra": "forbid"}

    name: str | None = Field(default=None, max_length=255)
    role: str | None = None
    is_active: bool | None = None
    password: str | None = Field(default=None, min_length=8)


class RetentionBody(BaseModel):
    recording_retention_days: int | None = None
    transcript_retention_days: int | None = None
    audit_retention_days: int | None = None


class CallQualityBody(BaseModel):
    model_config = {"extra": "forbid"}

    quality_score: int | None = Field(default=None, ge=1, le=5)
    disposition_code: str | None = Field(default=None, max_length=64)
    quality_notes: str | None = Field(default=None, max_length=2000)


@router.get("/customers")
def customers(
    user: CurrentUser = Depends(_require_customers_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"customers": AdminRepository(session).list_customers(user.tenant_id)}


@router.get("/calls")
def calls(
    user: CurrentUser = Depends(_require_calls_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    status: str | None = Query(
        default=None,
        max_length=32,
        description="Optional status filter (e.g. active for live monitoring)",
    ),
    limit: int = Query(default=100, ge=1, le=200),
    cursor: str | None = Query(default=None, max_length=512),
) -> dict[str, Any]:
    try:
        page = AdminRepository(session).list_calls(
            user.tenant_id, status=status, limit=limit, cursor=cursor
        )
        return page
    except AdminError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.patch("/calls/{call_id}/quality")
def review_call_quality(
    call_id: UUID,
    body: CallQualityBody,
    user: CurrentUser = Depends(_require_calls_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    try:
        call = AdminRepository(session).review_call_quality(
            user.tenant_id,
            call_id,
            actor=user.email,
            quality_score=body.quality_score,
            disposition_code=body.disposition_code,
            quality_notes=body.quality_notes,
        )
        return {"call": call}
    except AdminError as exc:
        status = 404 if exc.code == "call_not_found" else 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.get("/appointments")
def appointments(
    user: CurrentUser = Depends(_require_appointments_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"appointments": AdminRepository(session).list_appointments(user.tenant_id)}


@router.get("/metrics")
def metrics(
    days: int = 30,
    user: CurrentUser = Depends(_require_analytics_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {
        "metrics": AdminRepository(session).metrics_summary(user.tenant_id, days=days)
    }


def _parse_optional_date(value: str | None, *, field: str) -> date | None:
    if value is None or not value.strip():
        return None
    try:
        return date.fromisoformat(value.strip())
    except ValueError as exc:
        raise HTTPException(
            status_code=400,
            detail={"code": "invalid_date", "message": f"Invalid {field} (YYYY-MM-DD)"},
        ) from exc


@router.get("/analytics")
def analytics_overview(
    preset: str = Query(default="last_30_days", max_length=32),
    from_date: str | None = Query(default=None, max_length=16),
    to_date: str | None = Query(default=None, max_length=16),
    user: CurrentUser = Depends(_require_analytics_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    """Phase 27 overview: calls + sales + operations for a tenant-local range."""
    try:
        return AnalyticsService(session).overview(
            user.tenant_id,
            preset=preset,
            from_date=_parse_optional_date(from_date, field="from_date"),
            to_date=_parse_optional_date(to_date, field="to_date"),
        )
    except AnalyticsRangeError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.get("/analytics/{section}")
def analytics_section(
    section: Literal["calls", "sales", "operations"],
    preset: str = Query(default="last_30_days", max_length=32),
    from_date: str | None = Query(default=None, max_length=16),
    to_date: str | None = Query(default=None, max_length=16),
    user: CurrentUser = Depends(_require_analytics_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    """Phase 27 section analytics (calls | sales | operations)."""
    svc = AnalyticsService(session)
    kwargs = {
        "preset": preset,
        "from_date": _parse_optional_date(from_date, field="from_date"),
        "to_date": _parse_optional_date(to_date, field="to_date"),
    }
    try:
        if section == "calls":
            return svc.calls_section(user.tenant_id, **kwargs)
        if section == "sales":
            return svc.sales_section(user.tenant_id, **kwargs)
        return svc.operations_section(user.tenant_id, **kwargs)
    except AnalyticsRangeError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.get(
    "/cogs/summary",
    dependencies=[Depends(require_platform_operator)],
)
def cogs_summary(
    session: Session = Depends(db_dep),  # noqa: B008
    tenant_id: UUID = Query(..., description="Target organization (platform only)"),
    period: str = Query(default="this_month", max_length=32),
    start: str | None = Query(default=None, max_length=64),
    end: str | None = Query(default=None, max_length=64),
) -> dict[str, Any]:
    """Platform-only estimated voice COGS. Organization Owner is never sufficient."""
    from datetime import datetime

    from callbot_platform.billing.cogs.service import CogsService

    start_dt = None
    end_dt = None
    try:
        if start:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if end:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        summary = CogsService(session).tenant_summary(
            tenant_id,
            period=period,
            start=start_dt,
            end=end_dt,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_period", "message": str(exc)}
        ) from exc
    return {"cogs": summary, "boundary": "platform"}


@router.get("/usage-cost/summary")
def usage_cost_summary(
    user: CurrentUser = Depends(_require_billing_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    """Customer-facing usage + plan limits (no platform COGS/margin/provider costs)."""
    from callbot_platform.billing.usage_ledger import (
        UsageAlertService,
        UsageCostAggregationService,
        ingest_storage_snapshot,
    )

    try:
        ingest_storage_snapshot(session, user.tenant_id)
    except Exception:
        pass
    summary = UsageCostAggregationService(session).customer_usage_summary(
        user.tenant_id
    )
    limits = UsageAlertService(session).limit_status(user.tenant_id)
    return {"usage_cost": summary, "limit_status": limits}


@router.get("/usage-cost/alerts")
def usage_cost_alerts(
    user: CurrentUser = Depends(_require_billing_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    evaluate: bool = Query(default=False),
) -> dict[str, Any]:
    """Usage limit status; optionally evaluate and enqueue threshold alerts."""
    from callbot_platform.billing.usage_ledger import UsageAlertService

    svc = UsageAlertService(session)
    status = svc.limit_status(user.tenant_id)
    fired: list[dict[str, Any]] = []
    if evaluate:
        fired = svc.evaluate_voice_limits(
            user.tenant_id,
            notify_email=getattr(user, "email", None),
        )
        session.commit()
    return {"limit_status": status, "alerts_fired": fired}


@router.get(
    "/usage-cost/platform-summary",
    dependencies=[Depends(require_platform_operator)],
)
def usage_cost_platform_summary(
    session: Session = Depends(db_dep),  # noqa: B008
    tenant_id: UUID = Query(..., description="Target organization (platform only)"),
) -> dict[str, Any]:
    """Full platform accounting for one org (COGS/margin). Not for organization sessions."""
    from callbot_platform.billing.usage_ledger import UsageCostAggregationService

    summary = UsageCostAggregationService(session).organization_summary(tenant_id)
    summary["boundary"] = "platform"
    return {"usage_cost": summary}


@router.get(
    "/usage-cost/fleet",
    dependencies=[Depends(require_platform_operator)],
)
def usage_cost_fleet(
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    """Cross-tenant COGS rollup — platform operators only."""
    from callbot_platform.billing.usage_ledger import UsageCostAggregationService

    return {"fleet": UsageCostAggregationService(session).fleet_summary()}


@router.get(
    "/cogs/scenarios",
    dependencies=[Depends(require_platform_operator)],
)
def cogs_scenarios(
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    """Platform-only rate-card modeling (config rates)."""
    from callbot_platform.billing.cogs.service import CogsService

    return {"scenarios": CogsService(session).scenarios(), "boundary": "platform"}


@router.get(
    "/cogs/calls",
    dependencies=[Depends(require_platform_operator)],
)
def cogs_calls(
    session: Session = Depends(db_dep),  # noqa: B008
    tenant_id: UUID = Query(..., description="Target organization (platform only)"),
    period: str = Query(default="this_month", max_length=32),
    start: str | None = Query(default=None, max_length=64),
    end: str | None = Query(default=None, max_length=64),
    channel: str | None = Query(default=None, max_length=32),
    transfer_kind: str | None = Query(default=None, max_length=16),
    call_id: str | None = Query(default=None, max_length=64),
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
) -> dict[str, Any]:
    """Platform-only paginated per-call estimated COGS."""
    from datetime import datetime

    from callbot_platform.billing.cogs.service import CogsService

    start_dt = None
    end_dt = None
    try:
        if start:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00"))
        if end:
            end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
        payload = CogsService(session).list_call_cogs(
            tenant_id,
            period=period,
            start=start_dt,
            end=end_dt,
            channel=channel,
            transfer_kind=transfer_kind,
            call_id=call_id,
            limit=limit,
            offset=offset,
        )
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_query", "message": str(exc)}
        ) from exc
    if isinstance(payload, dict):
        payload["boundary"] = "platform"
    return payload


@router.get(
    "/cogs/calls/{call_id}",
    dependencies=[Depends(require_platform_operator)],
)
def cogs_call_detail(
    call_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
    tenant_id: UUID = Query(..., description="Target organization (platform only)"),
) -> dict[str, Any]:
    """Platform-only single-call estimated COGS detail."""
    from callbot_platform.billing.cogs.service import CogsService

    detail = CogsService(session).get_call_cogs(tenant_id, call_id)
    if detail is None:
        raise HTTPException(
            status_code=404,
            detail={"code": "cogs_not_found", "message": "Call COGS not found"},
        )
    return {"call": detail, "boundary": "platform"}


@router.get("/supervisor")
def supervisor(
    user: CurrentUser = Depends(_require_calls_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    recent_limit: int = Query(default=20, ge=1, le=50),
) -> dict[str, Any]:
    """Supervisor read-only snapshot: live calls, recent history, handoff attention."""
    return {
        "snapshot": AdminRepository(session).supervisor_snapshot(
            user.tenant_id, recent_limit=recent_limit
        )
    }


class QueueCompleteBody(BaseModel):
    model_config = {"extra": "forbid"}

    notes: str | None = Field(default=None, max_length=2000)
    cancel: bool = False


@router.get("/queue")
def list_queue(
    user: CurrentUser = Depends(_require_handoff_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
    status: str | None = Query(default=None, max_length=32),
    limit: int = Query(default=50, ge=1, le=100),
) -> dict[str, Any]:
    from callbot_platform.queue import CallQueueRepository, QueueError

    try:
        return {
            "items": CallQueueRepository(session).list_items(
                user.tenant_id, status=status, limit=limit
            )
        }
    except QueueError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post("/queue/{item_id}/claim")
def claim_queue_item(
    item_id: UUID,
    user: CurrentUser = Depends(_require_handoff_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.queue import CallQueueRepository, QueueError

    try:
        item = CallQueueRepository(session).claim(
            user.tenant_id, item_id, actor=user.email
        )
        return {"item": item}
    except QueueError as exc:
        status = 404 if exc.code == "queue_item_not_found" else 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post("/queue/{item_id}/complete")
def complete_queue_item(
    item_id: UUID,
    body: QueueCompleteBody,
    user: CurrentUser = Depends(_require_handoff_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.queue import CallQueueRepository, QueueError

    try:
        item = CallQueueRepository(session).complete(
            user.tenant_id,
            item_id,
            actor=user.email,
            notes=body.notes,
            cancel=body.cancel,
        )
        return {"item": item}
    except QueueError as exc:
        status = 404 if exc.code == "queue_item_not_found" else 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.get("/audit")
def audit(
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"events": AdminRepository(session).list_audit(user.tenant_id)}


@router.get("/users")
def users(
    user: CurrentUser = Depends(_require_team_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"users": AdminRepository(session).list_users(user.tenant_id)}


@router.post("/users")
def invite_user(
    body: InviteUserBody,
    user: CurrentUser = Depends(_require_team_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    if body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    try:
        created = AuthRepository(session).create_user(
            user.tenant_id,
            email=body.email,
            password=body.password,
            name=body.name,
            role=body.role,
            phone=body.phone,
            actor=user.email,
        )
        return {"user": created}
    except AuthError as exc:
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.patch("/users/{user_id}")
def update_user(
    user_id: str,
    body: UpdateUserBody,
    user: CurrentUser = Depends(_require_team_manage),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    if body.role is not None and body.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    try:
        updated = AuthRepository(session).update_user_admin(
            user.tenant_id,
            UUID(user_id),
            actor_user_id=user.user_id,
            actor_email=user.email,
            role=body.role,
            is_active=body.is_active,
            name=body.name,
            password=body.password,
        )
        return {"user": updated}
    except AuthError as exc:
        status = 404 if exc.code == "user_not_found" else 400
        raise HTTPException(
            status_code=status, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    except ValueError as exc:
        raise HTTPException(
            status_code=400, detail={"code": "invalid_user_id", "message": str(exc)}
        ) from exc


@router.get("/retention")
def get_retention(
    user: CurrentUser = Depends(_require_org_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    return {"settings": AdminRepository(session).get_retention(user.tenant_id)}


@router.put("/retention")
def put_retention(
    body: RetentionBody,
    user: CurrentUser = Depends(_require_org_update),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    settings = AdminRepository(session).upsert_retention(
        user.tenant_id,
        recording_retention_days=body.recording_retention_days,
        transcript_retention_days=body.transcript_retention_days,
        audit_retention_days=body.audit_retention_days,
        actor=user.email,
    )
    return {"settings": settings}


class AgentSettingsUpdateBody(BaseModel):
    """Tenant-editable agent profile fields. tenant_id is never accepted."""

    model_config = {"extra": "forbid"}

    voice: str | None = None
    language: str | None = None
    greeting: str | None = None
    assistant_name: str | None = None
    business_description: str | None = None
    tone: str | None = None
    supported_languages: list[str] | None = None
    response_style: str | None = None
    service_areas: list[str] | None = None
    business_hours_summary: str | None = None
    booking_rules: str | None = None
    pricing_disclosure_policy: str | None = None
    handoff_rules_text: str | None = None
    restricted_topics: list[str] | None = None
    custom_instructions: str | None = None


@router.get("/agent-settings")
def get_agent_settings(
    user: CurrentUser = Depends(_require_ai_read),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.crm.repos import AgentSettingsRepository

    settings = AgentSettingsRepository(session).get(user.tenant_id)
    return {
        "settings": settings,
        "business_name": user.tenant_name,
    }


@router.put("/agent-settings")
def put_agent_settings(
    body: AgentSettingsUpdateBody,
    user: CurrentUser = Depends(_require_ai_configure),  # noqa: B008
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    """Admin-only. Always scoped to the session tenant — never path/body tenant_id."""
    from callbot_platform.api.crm_routes import (
        AgentSettingsBody,
        apply_agent_settings_upsert,
    )
    from callbot_platform.security.rate_limit import (
        AGENT_SETTINGS_RATE_LIMITER,
        RateLimitExceeded,
    )

    try:
        AGENT_SETTINGS_RATE_LIMITER.check(f"admin:{user.user_id}")
    except RateLimitExceeded as exc:
        raise HTTPException(
            status_code=429,
            detail={
                "code": "rate_limited",
                "message": "Too many agent settings updates. Try again shortly.",
            },
            headers={"Retry-After": str(int(exc.retry_after_sec) + 1)},
        ) from exc

    payload = AgentSettingsBody(**body.model_dump(exclude_unset=True))
    settings = apply_agent_settings_upsert(
        session,
        tenant_id=user.tenant_id,
        body=payload,
        actor=user.email,
    )
    return {"settings": settings, "business_name": user.tenant_name}


class AdminWalletAdjustBody(BaseModel):
    model_config = {"extra": "forbid"}

    amount_cents: int = Field(..., gt=0, le=5_000_000)
    reason: str = Field(..., min_length=3, max_length=500)
    idempotency_key: str = Field(..., min_length=8, max_length=128)


@router.get(
    "/wallets/{tenant_id}",
    dependencies=[Depends(require_platform_operator)],
)
def admin_get_wallet(
    tenant_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.billing.wallet.service import WalletService

    return {"wallet": WalletService(session).get_balance(tenant_id)}


@router.get(
    "/wallets/{tenant_id}/transactions",
    dependencies=[Depends(require_platform_operator)],
)
def admin_wallet_transactions(
    tenant_id: UUID,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.billing.wallet.service import WalletService

    return {
        "transactions": WalletService(session).list_transactions(
            tenant_id, limit=limit, offset=offset
        )
    }


@router.post(
    "/wallets/{tenant_id}/credit",
    dependencies=[Depends(require_platform_operator)],
)
def admin_wallet_credit(
    tenant_id: UUID,
    body: AdminWalletAdjustBody,
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.billing.wallet.service import WalletError, WalletService
    from callbot_platform.telephony.audit import write_audit

    actor = "platform_operator"
    try:
        txn = WalletService(session).credit(
            tenant_id,
            amount_cents=body.amount_cents,
            idempotency_key=f"admin_credit:{body.idempotency_key}",
            reference_type="ADMIN",
            reference_id=actor,
            description=body.reason,
            transaction_type="ADJUSTMENT",
        )
        write_audit(
            session,
            tenant_id=tenant_id,
            actor=actor,
            action="wallet_admin_credit",
            resource_ids={"amount_cents": body.amount_cents, "txn": str(txn.id)},
        )
        session.commit()
        return {
            "transaction_id": str(txn.id),
            "balance_after_cents": txn.balance_after_cents,
        }
    except WalletError as exc:
        session.rollback()
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post(
    "/wallets/{tenant_id}/debit",
    dependencies=[Depends(require_platform_operator)],
)
def admin_wallet_debit(
    tenant_id: UUID,
    body: AdminWalletAdjustBody,
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.billing.wallet.service import WalletError, WalletService
    from callbot_platform.telephony.audit import write_audit

    actor = "platform_operator"
    try:
        txn = WalletService(session).debit(
            tenant_id,
            amount_cents=body.amount_cents,
            idempotency_key=f"admin_debit:{body.idempotency_key}",
            reference_type="ADMIN",
            reference_id=actor,
            description=body.reason,
        )
        write_audit(
            session,
            tenant_id=tenant_id,
            actor=actor,
            action="wallet_admin_debit",
            resource_ids={"amount_cents": body.amount_cents, "txn": str(txn.id)},
        )
        session.commit()
        return {
            "transaction_id": str(txn.id),
            "balance_after_cents": txn.balance_after_cents,
        }
    except WalletError as exc:
        session.rollback()
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc


@router.post(
    "/wallets/{tenant_id}/freeze",
    dependencies=[Depends(require_platform_operator)],
)
def admin_wallet_freeze(
    tenant_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.billing.wallet.service import WalletService
    from callbot_platform.telephony.audit import write_audit

    actor = "platform_operator"
    wallet = WalletService(session).freeze(tenant_id, reason=f"admin:{actor}")
    write_audit(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action="wallet_admin_freeze",
        resource_ids={"wallet_id": str(wallet.id)},
    )
    session.commit()
    return {"status": wallet.status}


@router.post(
    "/wallets/{tenant_id}/unfreeze",
    dependencies=[Depends(require_platform_operator)],
)
def admin_wallet_unfreeze(
    tenant_id: UUID,
    session: Session = Depends(db_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.billing.wallet.service import WalletError, WalletService
    from callbot_platform.telephony.audit import write_audit

    actor = "platform_operator"
    try:
        wallet = WalletService(session).unfreeze(tenant_id)
    except WalletError as exc:
        session.rollback()
        raise HTTPException(
            status_code=400, detail={"code": exc.code, "message": str(exc)}
        ) from exc
    write_audit(
        session,
        tenant_id=tenant_id,
        actor=actor,
        action="wallet_admin_unfreeze",
        resource_ids={"wallet_id": str(wallet.id)},
    )
    session.commit()
    return {"status": wallet.status}


@router.post(
    "/billing/renewals/run",
    dependencies=[Depends(require_platform_operator)],
)
def admin_run_subscription_renewals(
    session: Session = Depends(db_dep),  # noqa: B008
    settings: Settings = Depends(settings_dep),  # noqa: B008
) -> dict[str, Any]:
    from callbot_platform.billing.renewal_jobs import (
        enqueue_subscription_renewal,
        run_renewal_and_alerts,
    )

    result = run_renewal_and_alerts(session)
    job = enqueue_subscription_renewal(session, settings=settings)
    session.commit()
    return {
        **result,
        "job_id": str(job.id) if job is not None else None,
    }
