"""Platform FastAPI application entrypoint."""

from __future__ import annotations

from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env.local")

from callbot_platform.api.routes import router  # noqa: E402
from callbot_platform.db import init_db  # noqa: E402

app = FastAPI(title="Call Bot Platform", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(router)


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

    from callbot_platform.config import get_settings

    settings = get_settings()
    uvicorn.run(
        "callbot_platform.main:app",
        host=settings.platform_api_host,
        port=settings.platform_api_port,
        reload=False,
    )


if __name__ == "__main__":
    main()
