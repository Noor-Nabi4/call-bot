"""Database session helpers."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from callbot_platform.config import get_settings
from callbot_platform.db.models import Base

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine(url: str | None = None):
    global _engine, _SessionLocal
    if _engine is None or url is not None:
        settings = get_settings()
        database_url = url or settings.database_url
        connect_args: dict = {}
        engine_kwargs: dict = {"future": True, "connect_args": connect_args}
        if database_url.startswith("sqlite"):
            connect_args["check_same_thread"] = False
            # StaticPool keeps a single connection so :memory: schemas persist.
            engine_kwargs["poolclass"] = StaticPool
        else:
            engine_kwargs.update(
                {
                    "pool_size": settings.db_pool_size,
                    "max_overflow": settings.db_max_overflow,
                    "pool_timeout": settings.db_pool_timeout,
                    "pool_recycle": settings.db_pool_recycle,
                    "pool_pre_ping": settings.db_pool_pre_ping,
                }
            )
        _engine = create_engine(database_url, **engine_kwargs)
        _SessionLocal = sessionmaker(
            bind=_engine, autoflush=False, autocommit=False, future=True
        )
    return _engine


def get_session_factory() -> sessionmaker[Session]:
    get_engine()
    assert _SessionLocal is not None
    return _SessionLocal


def init_db(url: str | None = None) -> None:
    engine = get_engine(url)
    Base.metadata.create_all(bind=engine)


def get_db() -> Generator[Session, None, None]:
    session = get_session_factory()()
    try:
        yield session
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
