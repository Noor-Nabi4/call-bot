import {
  Bot,
  BookOpen,
  Briefcase,
  Calendar,
  CreditCard,
  LayoutDashboard,
  LayoutGrid,
  Phone,
  PhoneCall,
  PhoneForwarded,
  Settings,
  Shield,
  ListOrdered,
  Store,
  KeyRound,
  Palette,
  Users,
  Wrench,
  BarChart3,
  Zap,
  CircleDollarSign,
} from "lucide-react";
import type { OpsUser } from "@/lib/api";
import {
  filterNavByPermission,
  isTechnicianShell,
} from "@/lib/permissions";

export type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutGrid;
  /** Effective permission key required to show this item (UX only). */
  permission?: string;
  section?: "work" | "ai" | "admin";
};

const OPS_NAV: NavItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
    section: "work",
  },
  {
    href: "/dispatch",
    label: "Dispatch",
    icon: LayoutGrid,
    permission: "jobs.read",
    section: "work",
  },
  {
    href: "/customers",
    label: "Customers",
    icon: Users,
    permission: "customers.read",
    section: "work",
  },
  {
    href: "/live",
    label: "Live",
    icon: PhoneCall,
    permission: "calls.read",
    section: "work",
  },
  {
    href: "/supervisor",
    label: "Supervisor",
    icon: Shield,
    permission: "handoff.read",
    section: "work",
  },
  {
    href: "/queue",
    label: "Queue",
    icon: ListOrdered,
    permission: "handoff.read",
    section: "work",
  },
  {
    href: "/calls",
    label: "Calls",
    icon: Phone,
    permission: "calls.read",
    section: "work",
  },
  {
    href: "/appointments",
    label: "Appointments",
    icon: Calendar,
    permission: "appointments.read",
    section: "work",
  },
  {
    href: "/metrics",
    label: "Metrics",
    icon: BarChart3,
    permission: "analytics.read",
    section: "work",
  },
  {
    href: "/playground",
    label: "Playground",
    icon: PhoneCall,
    permission: "ai.configure",
    section: "ai",
  },
  {
    href: "/agents",
    label: "Agents",
    icon: Bot,
    permission: "agents.manage",
    section: "ai",
  },
  {
    href: "/marketplace",
    label: "Marketplace",
    icon: Store,
    permission: "agents.manage",
    section: "ai",
  },
  {
    href: "/phones",
    label: "Phones",
    icon: Phone,
    permission: "phones.manage",
    section: "ai",
  },
  {
    href: "/knowledge",
    label: "Knowledge",
    icon: BookOpen,
    permission: "knowledge.read",
    section: "ai",
  },
  {
    href: "/handoff",
    label: "Handoff",
    icon: PhoneForwarded,
    permission: "handoff.read",
    section: "ai",
  },
  {
    href: "/settings",
    label: "Settings",
    icon: Settings,
    permission: "organization.read",
    section: "admin",
  },
  {
    href: "/settings/team",
    label: "Team",
    icon: Users,
    permission: "team.read",
    section: "admin",
  },
  {
    href: "/settings/roles",
    label: "Roles",
    icon: Shield,
    permission: "roles.read",
    section: "admin",
  },
  {
    href: "/settings/billing",
    label: "Billing",
    icon: CreditCard,
    permission: "billing.read",
    section: "admin",
  },
  {
    href: "/settings/cogs",
    label: "COGS & Profitability",
    icon: CircleDollarSign,
    permission: "billing.read",
    section: "admin",
  },
  {
    href: "/settings/automations",
    label: "Automations",
    icon: Zap,
    permission: "automations.read",
    section: "admin",
  },
  {
    href: "/settings/api-keys",
    label: "API keys",
    icon: KeyRound,
    permission: "api_keys.manage",
    section: "admin",
  },
  {
    href: "/settings/branding",
    label: "Branding",
    icon: Palette,
    permission: "branding.manage",
    section: "admin",
  },
  {
    href: "/tech",
    label: "Tech",
    icon: Wrench,
    permission: "jobs.read",
    section: "admin",
  },
];

const TECH_NAV: NavItem[] = [
  { href: "/tech", label: "Jobs", icon: Briefcase, permission: "jobs.read" },
];

export function navFor(user: OpsUser): NavItem[] {
  if (isTechnicianShell(user)) {
    return filterNavByPermission(user, TECH_NAV);
  }
  return filterNavByPermission(user, OPS_NAV);
}

export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  if (href === "/dispatch") {
    return pathname === "/dispatch" || pathname === "/board";
  }
  if (href === "/agents") {
    return pathname === "/agents" || pathname.startsWith("/agents/");
  }
  if (href === "/playground") {
    return pathname === "/playground" || pathname.startsWith("/playground/");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
