"""Platform FastAPI application entrypoint."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env.local")

from callbot_platform.api.admin_routes import router as admin_router  # noqa: E402
from callbot_platform.api.auth_routes import router as auth_router  # noqa: E402
from callbot_platform.api.billing_routes import router as billing_router  # noqa: E402
from callbot_platform.api.crm_routes import (  # noqa: E402
    internal_tenant_router,
    router as crm_router,
    tenant_settings_router,
)
from callbot_platform.api.handoff_routes import (  # noqa: E402
    internal_router as handoff_internal_router,
)
from callbot_platform.api.handoff_routes import ops_router as handoff_ops_router  # noqa: E402
from callbot_platform.api.jobs_routes import router as jobs_router  # noqa: E402
from callbot_platform.api.knowledge_routes import (  # noqa: E402
    internal_router as knowledge_internal_router,
)
from callbot_platform.api.knowledge_routes import ops_router as knowledge_ops_router  # noqa: E402
from callbot_platform.api.routes import router  # noqa: E402
from callbot_platform.api.scheduling_routes import router as scheduling_router  # noqa: E402
from callbot_platform.config import get_settings  # noqa: E402
from callbot_platform.db import init_db  # noqa: E402

_settings = get_settings()
_cors_origins = list(_settings.ops_cors_origin_list)
for _extra in (
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:3002",
    "http://127.0.0.1:3000",
    "http://127.0.0.1:3001",
    "http://127.0.0.1:3002",
):
    if _extra not in _cors_origins:
        _cors_origins.append(_extra)

app = FastAPI(title="Call Bot Platform", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)
app.include_router(crm_router)
app.include_router(internal_tenant_router)
app.include_router(scheduling_router)
app.include_router(auth_router)
app.include_router(billing_router)
app.include_router(jobs_router)
app.include_router(knowledge_internal_router)
app.include_router(knowledge_ops_router)
app.include_router(handoff_internal_router)
app.include_router(handoff_ops_router)
app.include_router(admin_router)
app.include_router(tenant_settings_router)


@app.on_event("startup")
def on_startup() -> None:
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
    uvicorn.run(
        "callbot_platform.main:app",
        host=cfg.platform_api_host,
        port=cfg.platform_api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
