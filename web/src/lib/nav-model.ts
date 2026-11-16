/**
 * Section-wise navigation model (data only — no React/icons).
 * Permissions are evaluated per page; sections are visual grouping only.
 */

import type { OpsUser } from "../types";
import { filterNavByPermission } from "./permissions";

export type NavSectionId = "work" | "crm" | "ai" | "admin";

export type NavLeaf = {
  href: string;
  label: string;
  /** Icon key resolved in shell/nav.ts */
  icon: string;
  permission?: string;
  section: NavSectionId;
};

export const NAV_SECTION_ORDER: NavSectionId[] = ["work", "crm", "ai", "admin"];

export const NAV_SECTION_LABELS: Record<NavSectionId, string> = {
  work: "Work",
  crm: "CRM",
  ai: "AI",
  admin: "Admin",
};

/** Non-CRM workspace pages. */
export const WORK_LEAVES: NavLeaf[] = [
  { href: "/dashboard", label: "Dashboard", icon: "layout-dashboard", section: "work" },
  {
    href: "/live",
    label: "Live",
    icon: "phone-call",
    permission: "calls.read",
    section: "work",
  },
  {
    href: "/crm/scheduling",
    label: "Scheduling",
    icon: "calendar-days",
    permission: "appointments.read",
    section: "work",
  },
  {
    href: "/crm/dispatch",
    label: "Dispatch",
    icon: "truck",
    permission: "dispatch.read",
    section: "work",
  },
  {
    href: "/supervisor",
    label: "Supervisor",
    icon: "shield",
    permission: "handoff.read",
    section: "work",
  },
  {
    href: "/queue",
    label: "Queue",
    icon: "list-ordered",
    permission: "handoff.read",
    section: "work",
  },
  {
    href: "/analytics",
    label: "Analytics",
    icon: "chart",
    permission: "analytics.read",
    section: "work",
  },
];

/** Fallback CRM pages when tenant CRM config is unavailable. */
export const CRM_LEAVES: NavLeaf[] = [
  {
    href: "/customers",
    label: "Customers",
    icon: "users",
    permission: "customers.read",
    section: "crm",
  },
  {
    href: "/crm/leads",
    label: "Leads",
    icon: "user-plus",
    permission: "leads.read",
    section: "crm",
  },
  {
    href: "/crm/products",
    label: "Products",
    icon: "package",
    permission: "products.read",
    section: "crm",
  },
  {
    href: "/crm/services",
    label: "Services",
    icon: "wrench",
    permission: "services.read",
    section: "crm",
  },
  {
    href: "/crm/orders",
    label: "Orders",
    icon: "shopping-cart",
    permission: "orders.read",
    section: "crm",
  },
  {
    href: "/crm/jobs",
    label: "Jobs",
    icon: "briefcase-business",
    permission: "jobs.read",
    section: "crm",
  },
  {
    href: "/crm/appointments",
    label: "Appointments",
    icon: "calendar-days",
    permission: "appointments.read",
    section: "crm",
  },
  {
    href: "/calls",
    label: "Calls",
    icon: "phone",
    permission: "calls.read",
    section: "crm",
  },
  {
    href: "/crm/invoices",
    label: "Invoices",
    icon: "receipt",
    permission: "invoices.read",
    section: "crm",
  },
  {
    href: "/crm/handoffs",
    label: "Handoffs",
    icon: "phone-forwarded",
    permission: "handoffs.read",
    section: "crm",
  },
];

/**
 * CRM pages that are not (yet) platform CRM modules but stay in the shell
 * when dynamic configuration replaces CRM_LEAVES.
 */
export const CRM_STATIC_EXTRAS: NavLeaf[] = [
  {
    href: "/crm/handoffs",
    label: "Handoffs",
    icon: "phone-forwarded",
    permission: "handoffs.read",
    section: "crm",
  },
];

export const AI_LEAVES: NavLeaf[] = [
  {
    href: "/playground",
    label: "Playground",
    icon: "phone-call",
    permission: "ai.configure",
    section: "ai",
  },
  {
    href: "/agents",
    label: "Agents",
    icon: "bot",
    permission: "agents.manage",
    section: "ai",
  },
  {
    href: "/marketplace",
    label: "Marketplace",
    icon: "store",
    permission: "agents.manage",
    section: "ai",
  },
  {
    href: "/phones",
    label: "Phones",
    icon: "phone",
    permission: "phones.manage",
    section: "ai",
  },
  {
    href: "/knowledge",
    label: "Knowledge",
    icon: "book-open",
    permission: "knowledge.read",
    section: "ai",
  },
  {
    href: "/handoff",
    label: "Handoff settings",
    icon: "phone-forwarded",
    permission: "handoff.read",
    section: "ai",
  },
  {
    href: "/crm/communication-templates",
    label: "Comm templates",
    icon: "message-square",
    permission: "communication_templates.read",
    section: "ai",
  },
];

export const ADMIN_LEAVES: NavLeaf[] = [
  {
    href: "/settings",
    label: "Settings",
    icon: "settings",
    permission: "organization.read",
    section: "admin",
  },
  {
    href: "/settings/crm",
    label: "CRM modules",
    icon: "layout-grid",
    permission: "crm.configure",
    section: "admin",
  },
  {
    href: "/onboarding",
    label: "Onboarding",
    icon: "clipboard-list",
    permission: "organization.read",
    section: "admin",
  },
  {
    href: "/onboarding/ai-setup",
    label: "AI setup",
    icon: "sparkles",
    permission: "business_setup.read",
    section: "admin",
  },
  {
    href: "/settings/team",
    label: "Team",
    icon: "users",
    permission: "team.read",
    section: "admin",
  },
  {
    href: "/settings/roles",
    label: "Roles",
    icon: "shield",
    permission: "roles.read",
    section: "admin",
  },
  {
    href: "/settings/billing",
    label: "Billing",
    icon: "credit-card",
    permission: "billing.read",
    section: "admin",
  },
  {
    href: "/settings/usage",
    label: "Usage",
    icon: "circle-dollar",
    permission: "billing.read",
    section: "admin",
  },
  {
    href: "/settings/automations",
    label: "Automations",
    icon: "zap",
    permission: "automations.read",
    section: "admin",
  },
  {
    href: "/settings/api-keys",
    label: "API keys",
    icon: "key-round",
    permission: "api_keys.manage",
    section: "admin",
  },
  {
    href: "/settings/integrations",
    label: "Integrations",
    icon: "blocks",
    permission: "integrations.read",
    section: "admin",
  },
  {
    href: "/settings/branding",
    label: "Branding",
    icon: "palette",
    permission: "branding.manage",
    section: "admin",
  },
  {
    href: "/tech",
    label: "Tech",
    icon: "wrench",
    permission: "jobs.read",
    section: "admin",
  },
];

export type NavSectionLeaves = {
  id: NavSectionId;
  label: string;
  items: NavLeaf[];
};

/**
 * Filter each page by permission, then drop sections with zero visible pages.
 * Missing jobs.read hides Jobs — not the whole CRM section.
 */
export function sectionsFromLeaves(
  user: Pick<OpsUser, "permissions"> | null | undefined,
  leaves: NavLeaf[],
): NavSectionLeaves[] {
  const visible = filterNavByPermission(user, leaves);
  return NAV_SECTION_ORDER.map((id) => ({
    id,
    label: NAV_SECTION_LABELS[id],
    items: visible.filter((item) => item.section === id),
  })).filter((section) => section.items.length > 0);
}

/** Default org shell leaves (work + fallback CRM + AI + admin). */
export function defaultOrgLeaves(): NavLeaf[] {
  const seen = new Set<string>();
  const out: NavLeaf[] = [];
  for (const item of [...WORK_LEAVES, ...CRM_LEAVES, ...AI_LEAVES, ...ADMIN_LEAVES]) {
    if (seen.has(item.href)) continue;
    seen.add(item.href);
    out.push(item);
  }
  return out;
}
