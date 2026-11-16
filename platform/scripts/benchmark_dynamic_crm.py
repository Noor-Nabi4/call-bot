#!/usr/bin/env python3
"""Repeatable local Dynamic CRM performance harness (not CI-gated).

Usage (from platform/ with DATABASE_URL and migrations applied):

    .venv/bin/python scripts/benchmark_dynamic_crm.py --records 1000

Does not invent SLA numbers — prints wall-clock timings for local comparison.
"""

from __future__ import annotations

import argparse
import time
import uuid

from callbot_platform.crm_config import CrmSetupService
from callbot_platform.db import get_session_factory
from callbot_platform.db.models.tenant import Tenant
from callbot_platform.dynamic_crm import (
    CustomObjectService,
    EffectiveCrmConfigurationService,
    FieldDefinitionService,
    FieldValueService,
)
from callbot_platform.organization import OrganizationService


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--records", type=int, default=1000)
    args = parser.parse_args()
    n = max(10, min(args.records, 50_000))

    SessionLocal = get_session_factory()
    session = SessionLocal()
    try:
        tenant = Tenant(name="Bench CRM", slug=f"bench-crm-{uuid.uuid4().hex[:8]}")
        session.add(tenant)
        session.flush()
        OrganizationService(session).update(
            tenant.id,
            actor="bench",
            name="Bench CRM",
            industry="hvac",
            business_type="services",
        )
        CrmSetupService(session).setup(tenant.id, actor="bench")
        objs = CustomObjectService(session)
        definition = objs.create_definition(
            tenant.id, object_key="bench_asset", name="Asset", actor="bench"
        )
        FieldDefinitionService(session).create_field(
            tenant.id,
            owner_scope="object",
            owner_key="bench_asset",
            field_key="code",
            label="Code",
            field_type="TEXT",
            actor="bench",
        )
        oid = uuid.UUID(definition["id"])
        t0 = time.perf_counter()
        for i in range(n):
            rec = objs.create_record(
                tenant.id, oid, actor="bench", values={"code": f"A-{i:05d}"}
            )
            if i == 0:
                first_id = rec["id"]
        session.commit()
        insert_s = time.perf_counter() - t0

        t1 = time.perf_counter()
        EffectiveCrmConfigurationService(session).get(tenant.id)
        cfg_s = time.perf_counter() - t1

        t2 = time.perf_counter()
        EffectiveCrmConfigurationService(session).get(tenant.id)
        cfg_cached_s = time.perf_counter() - t2

        t3 = time.perf_counter()
        objs.list_records(tenant.id, oid, limit=50)
        list_s = time.perf_counter() - t3

        t4 = time.perf_counter()
        FieldValueService(session).find_record_ids(
            tenant.id,
            owner_scope="object",
            owner_key="bench_asset",
            filters=[{"field": "code", "operator": "equals", "value": "A-00042"}],
            limit=50,
        )
        filter_s = time.perf_counter() - t4

        print(
            f"records={n} insert={insert_s:.3f}s "
            f"config={cfg_s:.4f}s config_cached={cfg_cached_s:.4f}s "
            f"list50={list_s:.4f}s filter={filter_s:.4f}s first={first_id}"
        )
    finally:
        session.close()


if __name__ == "__main__":
    main()
