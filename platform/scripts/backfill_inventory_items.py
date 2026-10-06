"""Idempotent backfill: ensure active variants have inventory items.

Usage (from platform/):
  uv run python scripts/backfill_inventory_items.py [--tenant-id UUID]

Does not create balances. Reports counts only; commits when created > 0.
"""

from __future__ import annotations

import argparse
import uuid

from sqlalchemy import select

from callbot_platform.crm.inventory.items import InventoryItemService
from callbot_platform.db import get_session_factory, init_db
from callbot_platform.db.models import Tenant


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tenant-id", type=str, default=None)
    args = parser.parse_args()
    init_db()
    session = get_session_factory()()
    try:
        q = select(Tenant)
        if args.tenant_id:
            q = q.where(Tenant.id == uuid.UUID(args.tenant_id))
        tenants = list(session.scalars(q).all())
        svc = InventoryItemService(session)
        totals = {
            "variants_without_inventory_item_before": 0,
            "created": 0,
            "already_existing": 0,
            "failed": 0,
        }
        for tenant in tenants:
            report = svc.backfill_missing_for_tenant(tenant.id, actor="backfill-script")
            print(report)
            for k in totals:
                totals[k] += int(report[k])
        session.commit()
        print({"total": totals})
    finally:
        session.close()


if __name__ == "__main__":
    main()
