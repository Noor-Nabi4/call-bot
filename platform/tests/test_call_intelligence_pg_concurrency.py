"""PostgreSQL concurrency for Call Intelligence recording/transcript uniqueness."""

from __future__ import annotations

import os
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import pytest
from sqlalchemy import create_engine, select, text
from sqlalchemy.orm import sessionmaker

from callbot_platform.call_intelligence import CallIntelligenceService
from callbot_platform.config import Settings
from callbot_platform.db.models import Base, Call, Tenant
from callbot_platform.db.models.call_intelligence import CallTranscript
from callbot_platform.db.models.recordings import RecordingObject
from callbot_platform.storage import FilesystemObjectStorage

PG_URL = os.environ.get(
    "CALL_INTEL_PG_TEST_URL",
    os.environ.get(
        "JOBS_PG_TEST_URL",
        "postgresql+psycopg://noor@localhost:5432/call_bot_inventory_test",
    ),
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
    reason="PostgreSQL not available for call intelligence concurrency tests",
)


@pytest.fixture()
def pg_factory(tmp_path: Path):
    engine = create_engine(PG_URL, future=True, pool_size=10, max_overflow=5)
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    Base.metadata.create_all(bind=engine)
    # Partial unique indexes from migration 0051
    with engine.begin() as conn:
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_recording_objects_tenant_provider_rec
                ON recording_objects (tenant_id, provider, provider_recording_id)
                WHERE provider_recording_id IS NOT NULL
                """
            )
        )
        conn.execute(
            text(
                """
                CREATE UNIQUE INDEX IF NOT EXISTS uq_call_transcripts_tenant_recording
                ON call_transcripts (tenant_id, recording_id)
                WHERE recording_id IS NOT NULL AND deleted_at IS NULL
                  AND status IN ('PENDING','PROCESSING','COMPLETED')
                """
            )
        )
    factory = sessionmaker(bind=engine, autoflush=False, autocommit=False, future=True)
    yield factory, tmp_path
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    engine.dispose()


def test_concurrent_provider_recording_ingest(pg_factory) -> None:
    factory, tmp_path = pg_factory
    storage = FilesystemObjectStorage(str(tmp_path / "obj"))
    settings = Settings(
        call_transcription_provider="deterministic",
        call_analysis_provider="deterministic",
    )

    with factory() as session:
        tenant = Tenant(name="CI PG", slug=f"ci-pg-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        call = Call(
            tenant_id=tenant.id,
            room_name="r1",
            status="completed",
        )
        session.add(call)
        session.flush()
        tenant_id = tenant.id
        call_id = call.id
        session.commit()

    audio = b"\x07" * 2500
    provider_recording_id = f"prov-{uuid.uuid4().hex}"

    def worker(_: int) -> str:
        with factory() as session:
            svc = CallIntelligenceService(session, settings=settings, storage=storage)
            out = svc.recordings.ingest(
                tenant_id=tenant_id,
                call_id=call_id,
                data=audio,
                provider="twilio",
                provider_recording_id=provider_recording_id,
                actor="worker",
            )
            session.commit()
            return out["id"]

    ids: list[str] = []
    with ThreadPoolExecutor(max_workers=10) as pool:
        futs = [pool.submit(worker, i) for i in range(10)]
        for fut in as_completed(futs):
            ids.append(fut.result())

    assert len(set(ids)) == 1
    with factory() as session:
        rows = list(
            session.scalars(
                select(RecordingObject).where(
                    RecordingObject.tenant_id == tenant_id,
                    RecordingObject.provider_recording_id == provider_recording_id,
                )
            ).all()
        )
        assert len(rows) == 1


def test_concurrent_transcribe_one_transcript(pg_factory) -> None:
    factory, tmp_path = pg_factory
    storage = FilesystemObjectStorage(str(tmp_path / "obj"))
    settings = Settings(
        call_transcription_provider="deterministic",
        call_analysis_provider="deterministic",
    )

    with factory() as session:
        tenant = Tenant(name="CI PG2", slug=f"ci-pg2-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        call = Call(tenant_id=tenant.id, room_name="r2", status="completed")
        session.add(call)
        session.flush()
        svc = CallIntelligenceService(session, settings=settings, storage=storage)
        rec = svc.recordings.ingest(
            tenant_id=tenant.id,
            call_id=call.id,
            data=b"\x08" * 3000,
            provider="internal",
            provider_recording_id="t1",
            actor="setup",
        )
        session.commit()
        tenant_id = tenant.id
        recording_id = uuid.UUID(rec["id"])

    def worker(_: int) -> str:
        with factory() as session:
            svc = CallIntelligenceService(session, settings=settings, storage=storage)
            out = svc.run_transcribe_job(tenant_id=tenant_id, recording_id=recording_id)
            session.commit()
            return out["id"]

    ids: list[str] = []
    with ThreadPoolExecutor(max_workers=8) as pool:
        futs = [pool.submit(worker, i) for i in range(8)]
        for fut in as_completed(futs):
            ids.append(fut.result())

    assert len(set(ids)) == 1
    with factory() as session:
        rows = list(
            session.scalars(
                select(CallTranscript).where(
                    CallTranscript.tenant_id == tenant_id,
                    CallTranscript.recording_id == recording_id,
                )
            ).all()
        )
        assert len(rows) == 1
