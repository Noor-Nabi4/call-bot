import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  filterNavByPermission,
  hasPermission,
  isTechnicianShell,
} from "./permissions.ts";
import type { OpsUser } from "../types/index.ts";

function user(partial: Partial<OpsUser>): OpsUser {
  return {
    id: "1",
    tenant_id: "t",
    tenant_slug: "t",
    tenant_name: "T",
    email: "a@t.test",
    name: "A",
    role: "admin",
    technician_id: null,
    permissions: [],
    roles: [],
    ...partial,
  };
}

describe("filterNavByPermission", () => {
  const items = [
    { href: "/customers", permission: "customers.read" },
    { href: "/settings/billing", permission: "billing.read" },
    { href: "/dashboard" },
  ];

  it("hides billing without billing.read", () => {
    const u = user({
      permissions: [
        {
          key: "customers.read",
          resource: "customers",
          action: "read",
          scope: "ALL_ORGANIZATION",
        },
      ],
    });
    const hrefs = filterNavByPermission(u, items).map((i) => i.href);
    assert.ok(hrefs.includes("/customers"));
    assert.ok(hrefs.includes("/dashboard"));
    assert.ok(!hrefs.includes("/settings/billing"));
  });

  it("shows billing when permitted", () => {
    const u = user({
      permissions: [
        {
          key: "billing.read",
          resource: "billing",
          action: "read",
          scope: "ALL_ORGANIZATION",
        },
      ],
    });
    assert.ok(
      filterNavByPermission(u, items).some((i) => i.href === "/settings/billing"),
    );
  });
});

describe("technician shell nav intent", () => {
  it("technician shell is true without ops roles", () => {
    const u = user({
      role: "technician",
      roles: [{ id: "1", name: "Technician", system: true }],
      permissions: [
        {
          key: "jobs.read",
          resource: "jobs",
          action: "read",
          scope: "ASSIGNED",
        },
      ],
    });
    assert.equal(isTechnicianShell(u), true);
    assert.equal(hasPermission(u, "jobs.read"), true);
    assert.equal(hasPermission(u, "billing.read"), false);
  });
});
