import assert from "node:assert/strict";
import { describe, it } from "node:test";
import {
  hasAnyPermission,
  hasPermission,
  isTechnicianShell,
  permissionScope,
} from "./permissions.ts";
import type { OpsUser } from "../types/index.ts";

function user(
  partial: Partial<OpsUser> & { permissions?: OpsUser["permissions"]; roles?: OpsUser["roles"] },
): OpsUser {
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

describe("hasPermission", () => {
  it("returns false without permissions", () => {
    assert.equal(hasPermission(null, "customers.read"), false);
    assert.equal(hasPermission(user({}), "customers.read"), false);
  });

  it("matches by key", () => {
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
    assert.equal(hasPermission(u, "customers.read"), true);
    assert.equal(hasPermission(u, "billing.manage"), false);
  });

  it("hasAnyPermission", () => {
    const u = user({
      permissions: [
        {
          key: "calls.read",
          resource: "calls",
          action: "read",
          scope: "ALL_ORGANIZATION",
        },
      ],
    });
    assert.equal(hasAnyPermission(u, ["billing.read", "calls.read"]), true);
    assert.equal(hasAnyPermission(u, ["billing.read", "billing.manage"]), false);
  });
});

describe("isTechnicianShell", () => {
  it("detects technician-only role membership", () => {
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
        {
          key: "customers.read",
          resource: "customers",
          action: "read",
          scope: "ASSIGNED",
        },
      ],
    });
    assert.equal(isTechnicianShell(u), true);
  });

  it("does not treat admin+technician as tech shell", () => {
    const u = user({
      roles: [
        { id: "1", name: "Admin", system: true },
        { id: "2", name: "Technician", system: true },
      ],
      permissions: [
        {
          key: "jobs.read",
          resource: "jobs",
          action: "read",
          scope: "ALL_ORGANIZATION",
        },
        {
          key: "analytics.read",
          resource: "analytics",
          action: "read",
          scope: "ALL_ORGANIZATION",
        },
      ],
    });
    assert.equal(isTechnicianShell(u), false);
  });
});

describe("permissionScope", () => {
  it("returns scope for a key", () => {
    const u = user({
      permissions: [
        {
          key: "jobs.read",
          resource: "jobs",
          action: "read",
          scope: "ASSIGNED",
        },
      ],
    });
    assert.equal(permissionScope(u, "jobs.read"), "ASSIGNED");
    assert.equal(permissionScope(u, "jobs.update"), null);
  });
});
