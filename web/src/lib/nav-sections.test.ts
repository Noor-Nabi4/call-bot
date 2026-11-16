/**
 * Per-page permission filtering for sectioned nav.
 * Uses the same leaf permissions as src/lib/nav-model.ts (keep in sync).
 */
import assert from "node:assert/strict";
import { describe, it } from "node:test";
import type { OpsUser } from "../types/index.ts";
import { filterNavByPermission } from "./permissions.ts";

type Leaf = { href: string; label: string; permission?: string; section: string };

function user(keys: string[]): OpsUser {
  return {
    id: "1",
    tenant_id: "t",
    tenant_slug: "t",
    tenant_name: "T",
    email: "a@t.test",
    name: "A",
    role: "admin",
    technician_id: null,
    roles: [],
    permissions: keys.map((key) => {
      const [resource, action = "read"] = key.split(".");
      return { key, resource, action, scope: "ALL_ORGANIZATION" };
    }),
  };
}

/** Mirrors defaultOrgLeaves() in nav-model.ts */
const LEAVES: Leaf[] = [
  { href: "/dashboard", label: "Dashboard", section: "work" },
  { href: "/live", label: "Live", permission: "calls.read", section: "work" },
  {
    href: "/crm/scheduling",
    label: "Scheduling",
    permission: "appointments.read",
    section: "work",
  },
  {
    href: "/crm/dispatch",
    label: "Dispatch",
    permission: "dispatch.read",
    section: "work",
  },
  {
    href: "/analytics",
    label: "Analytics",
    permission: "analytics.read",
    section: "work",
  },
  {
    href: "/customers",
    label: "Customers",
    permission: "customers.read",
    section: "crm",
  },
  { href: "/crm/leads", label: "Leads", permission: "leads.read", section: "crm" },
  {
    href: "/crm/products",
    label: "Products",
    permission: "products.read",
    section: "crm",
  },
  {
    href: "/crm/services",
    label: "Services",
    permission: "services.read",
    section: "crm",
  },
  { href: "/crm/orders", label: "Orders", permission: "orders.read", section: "crm" },
  { href: "/crm/jobs", label: "Jobs", permission: "jobs.read", section: "crm" },
  {
    href: "/crm/appointments",
    label: "Appointments",
    permission: "appointments.read",
    section: "crm",
  },
  { href: "/calls", label: "Calls", permission: "calls.read", section: "crm" },
  {
    href: "/crm/invoices",
    label: "Invoices",
    permission: "invoices.read",
    section: "crm",
  },
  { href: "/dispatch", label: "Jobs board", permission: "jobs.read", section: "crm" },
  {
    href: "/playground",
    label: "Playground",
    permission: "ai.configure",
    section: "ai",
  },
  { href: "/agents", label: "Agents", permission: "agents.manage", section: "ai" },
  { href: "/phones", label: "Phones", permission: "phones.manage", section: "ai" },
  {
    href: "/knowledge",
    label: "Knowledge",
    permission: "knowledge.read",
    section: "ai",
  },
  {
    href: "/settings/team",
    label: "Team",
    permission: "team.read",
    section: "admin",
  },
  {
    href: "/settings/roles",
    label: "Roles",
    permission: "roles.read",
    section: "admin",
  },
  {
    href: "/settings/billing",
    label: "Billing",
    permission: "billing.read",
    section: "admin",
  },
  {
    href: "/settings/usage",
    label: "Usage",
    permission: "billing.read",
    section: "admin",
  },
  {
    href: "/settings/api-keys",
    label: "API keys",
    permission: "api_keys.manage",
    section: "admin",
  },
];

function visibleSections(u: OpsUser) {
  const items = filterNavByPermission(u, LEAVES);
  return ["work", "crm", "ai", "admin"]
    .map((id) => ({
      id,
      items: items.filter((i) => i.section === id),
    }))
    .filter((s) => s.items.length > 0);
}

function labels(sections: ReturnType<typeof visibleSections>, id: string) {
  return sections.find((s) => s.id === id)?.items.map((i) => i.label) ?? [];
}

describe("sectioned nav — per-page permission filtering", () => {
  it("User A: CRM shows Customers/Leads/Appointments only", () => {
    const sections = visibleSections(
      user(["customers.read", "leads.read", "appointments.read"]),
    );
    const l = labels(sections, "crm");
    assert.ok(sections.some((s) => s.id === "crm"));
    assert.deepEqual(l.sort(), ["Appointments", "Customers", "Leads"].sort());
  });

  it("User B: only jobs.read keeps CRM with Jobs", () => {
    const sections = visibleSections(user(["jobs.read"]));
    const l = labels(sections, "crm");
    assert.ok(sections.some((s) => s.id === "crm"));
    assert.ok(l.includes("Jobs"));
    assert.ok(l.includes("Jobs board"));
    assert.ok(!l.includes("Customers"));
  });

  it("User C: no CRM permissions hides CRM section", () => {
    const sections = visibleSections(user(["analytics.read"]));
    assert.ok(!sections.some((s) => s.id === "crm"));
  });

  it("User D: AI shows Playground+Knowledge subset", () => {
    const sections = visibleSections(user(["ai.configure", "knowledge.read"]));
    const l = labels(sections, "ai");
    assert.deepEqual(l.sort(), ["Knowledge", "Playground"].sort());
  });

  it("User E: Admin shows Team/Billing/Usage", () => {
    const sections = visibleSections(user(["team.read", "billing.read"]));
    const l = labels(sections, "admin");
    assert.deepEqual(l.sort(), ["Billing", "Team", "Usage"].sort());
  });

  it("User F: Work shows Dashboard/Scheduling/Analytics", () => {
    const sections = visibleSections(
      user(["analytics.read", "appointments.read"]),
    );
    const l = labels(sections, "work");
    assert.ok(l.includes("Dashboard"));
    assert.ok(l.includes("Scheduling"));
    assert.ok(l.includes("Analytics"));
    assert.ok(!l.includes("Live"));
    assert.ok(!l.includes("Dispatch"));
  });

  it("missing jobs.read does not hide CRM when other CRM pages remain", () => {
    const sections = visibleSections(user(["customers.read"]));
    assert.ok(sections.some((s) => s.id === "crm"));
    assert.deepEqual(labels(sections, "crm"), ["Customers"]);
  });
});
