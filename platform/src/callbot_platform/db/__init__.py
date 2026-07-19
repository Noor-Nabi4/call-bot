"""Database session helpers."""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.config import get_settings
from callbot_platform.db.models import Base

_engine = None
_SessionLocal: sessionmaker[Session] | None = None


def get_engine(url: str | None = None):
    global _engine, _SessionLocal
    if _engine is None or url is not None:
        database_url = url or get_settings().database_url
        connect_args = {}
        if database_url.startswith("sqlite"):
            connect_args = {"check_same_thread": False}
        _engine = create_engine(database_url, future=True, connect_args=connect_args)
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
