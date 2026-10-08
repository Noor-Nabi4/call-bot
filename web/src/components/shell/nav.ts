import {
  Badge,
  Bot,
  BookOpen,
  Briefcase,
  BriefcaseBusiness,
  Building2,
  Calendar,
  CalendarDays,
  ChartNoAxesCombined,
  CheckSquare,
  ClipboardList,
  CreditCard,
  Cpu,
  FileText,
  Folder,
  Handshake,
  HardHat,
  Home,
  Layers,
  LayoutDashboard,
  LayoutGrid,
  ListOrdered,
  MessageSquare,
  Package,
  Percent,
  Phone,
  PhoneCall,
  PhoneForwarded,
  Receipt,
  RotateCcw,
  Settings,
  Shield,
  ShoppingCart,
  Store,
  KeyRound,
  Palette,
  Sparkles,
  Truck,
  Users,
  UserPlus,
  Wrench,
  Zap,
  CircleDollarSign,
  Box,
  Blocks,
  type LucideIcon,
} from "lucide-react";
import type { OpsUser } from "@/lib/api";
import {
  filterNavByPermission,
  isTechnicianShell,
} from "@/lib/permissions";
import type { CrmNavItem } from "@/lib/crm/use-crm-configuration";

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Effective permission key required to show this item (UX only). */
  permission?: string;
  section?: "work" | "ai" | "admin";
};

const ICON_BY_NAME: Record<string, LucideIcon> = {
  users: Users,
  building: Building2,
  "user-plus": UserPlus,
  handshake: Handshake,
  package: Package,
  wrench: Wrench,
  "shopping-cart": ShoppingCart,
  briefcase: Briefcase,
  calendar: Calendar,
  "calendar-days": CalendarDays,
  "briefcase-business": BriefcaseBusiness,
  truck: Truck,
  "file-text": FileText,
  receipt: Receipt,
  "credit-card": CreditCard,
  cpu: Cpu,
  badge: Badge,
  phone: Phone,
  "message-square": MessageSquare,
  "check-square": CheckSquare,
  folder: Folder,
  layers: Layers,
  map: LayoutGrid,
  "hard-hat": HardHat,
  home: Home,
  "rotate-ccw": RotateCcw,
  percent: Percent,
  box: Box,
};

export function iconForCrm(name?: string | null): LucideIcon {
  if (!name) return Box;
  return ICON_BY_NAME[name] || Box;
}

/** Non-CRM workspace items that stay static. */
const STATIC_WORK_NAV: NavItem[] = [
  {
    href: "/dashboard",
    label: "Dashboard",
    icon: LayoutDashboard,
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
    href: "/crm/scheduling",
    label: "Scheduling",
    icon: CalendarDays,
    permission: "appointments.read",
    section: "work",
  },
  {
    href: "/crm/dispatch",
    label: "Dispatch",
    icon: Truck,
    permission: "dispatch.read",
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
    href: "/analytics",
    label: "Analytics",
    icon: ChartNoAxesCombined,
    permission: "analytics.read",
    section: "work",
  },
];

/** Legacy hardcoded CRM paths — used only when effective config is unavailable. */
const FALLBACK_CRM_NAV: NavItem[] = [
  {
    href: "/customers",
    label: "Customers",
    icon: Users,
    permission: "customers.read",
    section: "work",
  },
  {
    href: "/crm/leads",
    label: "Leads",
    icon: UserPlus,
    permission: "leads.read",
    section: "work",
  },
  {
    href: "/crm/products",
    label: "Products",
    icon: Package,
    permission: "products.read",
    section: "work",
  },
  {
    href: "/crm/services",
    label: "Services",
    icon: Wrench,
    permission: "services.read",
    section: "work",
  },
  {
    href: "/crm/orders",
    label: "Orders",
    icon: ShoppingCart,
    permission: "orders.read",
    section: "work",
  },
  {
    href: "/crm/jobs",
    label: "Jobs",
    icon: BriefcaseBusiness,
    permission: "jobs.read",
    section: "work",
  },
  {
    href: "/crm/appointments",
    label: "Appointments",
    icon: CalendarDays,
    permission: "appointments.read",
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
    href: "/crm/invoices",
    label: "Invoices",
    icon: Receipt,
    permission: "invoices.read",
    section: "work",
  },
  {
    href: "/dispatch",
    label: "Jobs board",
    icon: LayoutGrid,
    permission: "jobs.read",
    section: "work",
  },
  {
    href: "/crm/handoffs",
    label: "Handoffs queue",
    icon: PhoneForwarded,
    permission: "handoffs.read",
    section: "work",
  },
];

const AI_NAV: NavItem[] = [
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
    label: "Handoff settings",
    icon: PhoneForwarded,
    permission: "handoff.read",
    section: "ai",
  },
  {
    href: "/crm/handoffs",
    label: "Handoffs queue",
    icon: Handshake,
    permission: "handoffs.read",
    section: "ai",
  },
  {
    href: "/crm/communication-templates",
    label: "Comm templates",
    icon: MessageSquare,
    permission: "communication_templates.read",
    section: "ai",
  },
];

const ADMIN_NAV: NavItem[] = [
  {
    href: "/settings",
    label: "Settings",
    icon: Settings,
    permission: "organization.read",
    section: "admin",
  },
  {
    href: "/settings/crm",
    label: "CRM modules",
    icon: LayoutGrid,
    permission: "crm.configure",
    section: "admin",
  },
  {
    href: "/onboarding",
    label: "Onboarding",
    icon: ClipboardList,
    permission: "organization.read",
    section: "admin",
  },
  {
    href: "/onboarding/ai-setup",
    label: "AI setup",
    icon: Sparkles,
    permission: "business_setup.read",
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
    href: "/settings/usage",
    label: "Usage",
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
    href: "/settings/integrations",
    label: "Integrations",
    icon: Blocks,
    permission: "integrations.read",
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

export function crmNavToItems(items: CrmNavItem[]): NavItem[] {
  const seen = new Set<string>();
  const out: NavItem[] = [];
  for (const item of items) {
    if (!item.href || seen.has(item.href)) continue;
    seen.add(item.href);
    out.push({
      href: item.href,
      label: item.label,
      icon: iconForCrm(item.icon),
      permission: item.permission || undefined,
      section: "work",
    });
  }
  return out;
}

export function navFor(
  user: OpsUser,
  crmNavigation?: CrmNavItem[] | null,
): NavItem[] {
  if (isTechnicianShell(user)) {
    return filterNavByPermission(user, TECH_NAV);
  }
  const crmItems =
    crmNavigation && crmNavigation.length > 0
      ? crmNavToItems(crmNavigation)
      : FALLBACK_CRM_NAV;
  const seen = new Set<string>();
  const merged: NavItem[] = [];
  for (const item of [
    ...STATIC_WORK_NAV,
    ...crmItems,
    ...AI_NAV,
    ...ADMIN_NAV,
  ]) {
    if (seen.has(item.href)) continue;
    seen.add(item.href);
    merged.push(item);
  }
  return filterNavByPermission(user, merged);
}

export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  if (href === "/analytics") {
    return pathname === "/analytics" || pathname.startsWith("/analytics/");
  }
  if (href === "/crm/scheduling") {
    return (
      pathname === "/crm/scheduling" || pathname.startsWith("/crm/scheduling/")
    );
  }
  if (href === "/crm/dispatch") {
    return pathname === "/crm/dispatch" || pathname.startsWith("/crm/dispatch/");
  }
  if (href === "/dispatch") {
    return pathname === "/dispatch" || pathname === "/board";
  }
  if (href === "/agents") {
    return pathname === "/agents" || pathname.startsWith("/agents/");
  }
  if (href === "/playground") {
    return pathname === "/playground" || pathname.startsWith("/playground/");
  }
  if (href.startsWith("/crm/")) {
    return pathname === href || pathname.startsWith(`${href}/`);
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
