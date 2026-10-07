"""Platform FastAPI application entrypoint."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env.local")

from callbot_platform.api.admin_routes import router as admin_router  # noqa: E402
from callbot_platform.api.agent_admin_routes import (
    router as agent_admin_router,
)
from callbot_platform.api.ai_tools_routes import (  # noqa: E402
    router as ai_tools_router,
)
from callbot_platform.api.api_key_admin_routes import (
    router as api_key_admin_router,
)
from callbot_platform.api.appointments_crm_routes import (  # noqa: E402
    router as appointments_crm_router,
)
from callbot_platform.api.auth_routes import router as auth_router  # noqa: E402
from callbot_platform.api.automation_routes import (
    router as automation_router,
)
from callbot_platform.api.billing_routes import router as billing_router  # noqa: E402
from callbot_platform.api.branding_routes import router as branding_router  # noqa: E402
from callbot_platform.api.business_config_routes import (  # noqa: E402
    router as business_config_router,
)
from callbot_platform.api.crm_routes import (  # noqa: E402
    internal_tenant_router,
    tenant_settings_router,
)
from callbot_platform.api.crm_routes import (
    router as crm_router,
)
from callbot_platform.api.customer_crm_routes import (  # noqa: E402
    router as customer_crm_router,
)
from callbot_platform.api.dispatch_crm_routes import (  # noqa: E402
    router as dispatch_crm_router,
)
from callbot_platform.api.dynamic_crm_routes import (  # noqa: E402
    router as dynamic_crm_router,
)
from callbot_platform.api.estimates_routes import (  # noqa: E402
    router as estimates_router,
)
from callbot_platform.api.invoices_routes import (  # noqa: E402
    router as invoices_router,
)
from callbot_platform.api.payments_routes import (  # noqa: E402
    router as payments_router,
)
from callbot_platform.api.memberships_routes import (  # noqa: E402
    router as memberships_router,
)
from callbot_platform.api.equipment_routes import (  # noqa: E402
    router as equipment_router,
)
from callbot_platform.api.handoff_routes import (  # noqa: E402
    internal_router as handoff_internal_router,
)
from callbot_platform.api.handoff_routes import (
    ops_router as handoff_ops_router,
)
from callbot_platform.api.inventory_routes import (  # noqa: E402
    router as inventory_router,
)
from callbot_platform.api.jobs_admin_routes import (  # noqa: E402
    router as jobs_admin_router,
)
from callbot_platform.api.jobs_crm_routes import (  # noqa: E402
    router as jobs_crm_router,
)
from callbot_platform.api.jobs_routes import router as jobs_router  # noqa: E402
from callbot_platform.api.knowledge_routes import (  # noqa: E402
    internal_router as knowledge_internal_router,
)
from callbot_platform.api.knowledge_routes import (
    ops_router as knowledge_ops_router,
)
from callbot_platform.api.leads_routes import (  # noqa: E402
    router as leads_router,
)
from callbot_platform.api.onboarding_routes import (  # noqa: E402
    router as onboarding_router,
)
from callbot_platform.api.orders_routes import (  # noqa: E402
    router as orders_router,
)
from callbot_platform.api.organization_routes import (  # noqa: E402
    router as organization_router,
)
from callbot_platform.api.product_catalog_routes import (  # noqa: E402
    router as product_catalog_router,
)
from callbot_platform.api.rbac_routes import (  # noqa: E402
    router as rbac_router,
)
from callbot_platform.api.routes import router  # noqa: E402
from callbot_platform.api.scheduling_routes import (
    router as scheduling_router,
)
from callbot_platform.api.services_pricebook_routes import (  # noqa: E402
    router as services_pricebook_router,
)
from callbot_platform.api.sms_webhook_routes import (  # noqa: E402
    router as sms_webhook_router,
)
from callbot_platform.api.v1_routes import router as v1_router  # noqa: E402
from callbot_platform.config import (  # noqa: E402
    get_settings,
    require_production_settings,
)
from callbot_platform.db import init_db  # noqa: E402
from callbot_platform.origins import (  # noqa: E402
    PROD_API_HOST,
    cors_allow_origins,
)

_settings = get_settings()
_cors_origins = cors_allow_origins(_settings)

app = FastAPI(title="Call & Flow Platform", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
if _settings.is_production:
    from starlette.middleware.trustedhost import TrustedHostMiddleware

    app.add_middleware(
        TrustedHostMiddleware,
        allowed_hosts=[PROD_API_HOST, "localhost", "127.0.0.1", "testserver"],
    )
app.include_router(router)
app.include_router(crm_router)
app.include_router(ai_tools_router)
app.include_router(sms_webhook_router)
app.include_router(internal_tenant_router)
app.include_router(scheduling_router)
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(branding_router)
app.include_router(organization_router)
app.include_router(onboarding_router)
app.include_router(business_config_router)
app.include_router(dynamic_crm_router)
app.include_router(customer_crm_router)
app.include_router(product_catalog_router)
app.include_router(inventory_router)
app.include_router(services_pricebook_router)
app.include_router(leads_router)
app.include_router(orders_router)
app.include_router(estimates_router)
app.include_router(invoices_router)
app.include_router(payments_router)
app.include_router(memberships_router)
app.include_router(equipment_router)
app.include_router(rbac_router)
app.include_router(jobs_router)
app.include_router(jobs_crm_router)
app.include_router(jobs_admin_router)
app.include_router(appointments_crm_router)
app.include_router(dispatch_crm_router)
app.include_router(knowledge_internal_router)
app.include_router(knowledge_ops_router)
app.include_router(handoff_internal_router)
app.include_router(handoff_ops_router)
app.include_router(admin_router)
app.include_router(agent_admin_router)
app.include_router(api_key_admin_router)
app.include_router(automation_router)
app.include_router(tenant_settings_router)
app.include_router(v1_router)


@app.on_event("startup")
def on_startup() -> None:
    if _settings.is_production:
        return
    # Dev convenience: create tables if missing. Prefer Alembic in production.
    try:
        init_db()
    except Exception:
        # DB may be unavailable at import-time in some test harnesses.
        pass


def main() -> None:
    import uvicorn

    from callbot_platform.config import get_settings as gs

    cfg = gs()
    require_production_settings(cfg)
    uvicorn.run(
        "callbot_platform.main:app",
        host=cfg.platform_api_host,
        port=cfg.platform_api_port,
        reload=False,
        proxy_headers=True,
        forwarded_allow_ips="*",
    )


if __name__ == "__main__":
    main()
