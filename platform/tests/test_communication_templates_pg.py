"""PostgreSQL verification for Phase 25 communication templates (constraints + EXPLAIN)."""

from __future__ import annotations

import os
import uuid

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from callbot_platform.db.models import Base, Tenant
from callbot_platform.db.models.communication_templates import (
    CommunicationTemplate,
    CommunicationTemplateVersion,
)

PG_URL = os.environ.get(
    "COMM_TEMPLATES_PG_TEST_URL",
    "postgresql+psycopg://noor@localhost:5432/call_bot_comm_templates_test",
)


def _pg_available(url: str) -> bool:
    try:
        engine = create_engine(url, future=True)
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        engine.dispose()
    except Exception:
        return False
    return True


pytestmark = pytest.mark.skipif(
    not _pg_available(PG_URL),
    reason="PostgreSQL not available for communication template PG tests",
)


@pytest.fixture()
def pg_factory():
    engine = create_engine(PG_URL, future=True, pool_size=5, max_overflow=2)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(bind=engine)
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def test_unique_template_key_and_version(pg_factory) -> None:
    session: Session = pg_factory()
    try:
        tenant = Tenant(name="CT PG", slug=f"ct-pg-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        tmpl = CommunicationTemplate(
            tenant_id=tenant.id,
            channel="SMS",
            template_key="BOOKING_CONFIRMATION",
            name="Booking",
            status="ACTIVE",
            active_version=1,
        )
        session.add(tmpl)
        session.flush()
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                CommunicationTemplate(
                    tenant_id=tenant.id,
                    channel="SMS",
                    template_key="BOOKING_CONFIRMATION",
                    name="Dup",
                    status="ACTIVE",
                    active_version=1,
                )
            )
            session.flush()
        session.add(
            CommunicationTemplateVersion(
                tenant_id=tenant.id,
                template_id=tmpl.id,
                version=1,
                body_template="Hi {{customer.first_name}}",
                status="ACTIVE",
            )
        )
        session.flush()
        with pytest.raises(IntegrityError), session.begin_nested():
            session.add(
                CommunicationTemplateVersion(
                    tenant_id=tenant.id,
                    template_id=tmpl.id,
                    version=1,
                    body_template="dup",
                    status="DRAFT",
                )
            )
            session.flush()
        session.commit()
    finally:
        session.close()


def test_explain_hot_paths_use_indexes(pg_factory) -> None:
    session: Session = pg_factory()
    try:
        tenant = Tenant(name="CT EX", slug=f"ct-ex-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        tmpl = CommunicationTemplate(
            tenant_id=tenant.id,
            channel="SMS",
            template_key="BOOKING_CONFIRMATION",
            name="Booking",
            status="ACTIVE",
            active_version=1,
        )
        session.add(tmpl)
        session.flush()
        session.add(
            CommunicationTemplateVersion(
                tenant_id=tenant.id,
                template_id=tmpl.id,
                version=1,
                body_template="Hi",
                status="ACTIVE",
            )
        )
        session.commit()

        engine = session.get_bind()
        with engine.connect() as conn:
            by_key = "\n".join(
                r[0]
                for r in conn.execute(
                    text(
                        "EXPLAIN (FORMAT TEXT) SELECT * FROM communication_templates "
                        "WHERE tenant_id = :tid AND channel='SMS' "
                        "AND template_key='BOOKING_CONFIRMATION'"
                    ),
                    {"tid": tenant.id},
                )
            )
            assert "Index Scan" in by_key or "Bitmap Index Scan" in by_key
            assert "ix_communication_templates_tenant_channel_key" in by_key

            version = "\n".join(
                r[0]
                for r in conn.execute(
                    text(
                        "EXPLAIN (FORMAT TEXT) SELECT * FROM communication_template_versions "
                        "WHERE template_id = :tid AND version = 1"
                    ),
                    {"tid": tmpl.id},
                )
            )
            assert "Index Scan" in version or "Bitmap Index Scan" in version
    finally:
        session.close()
