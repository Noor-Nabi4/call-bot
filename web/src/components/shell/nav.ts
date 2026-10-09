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
import {
  AI_LEAVES,
  ADMIN_LEAVES,
  CRM_LEAVES,
  NAV_SECTION_LABELS,
  NAV_SECTION_ORDER,
  WORK_LEAVES,
  defaultOrgLeaves,
  sectionsFromLeaves,
  type NavLeaf,
  type NavSectionId,
} from "@/lib/nav-model";

export type { NavSectionId };

export type NavItem = {
  href: string;
  label: string;
  icon: LucideIcon;
  /** Effective permission key required to show this item (UX only). */
  permission?: string;
  /** Visual grouping only — never used as authorization. */
  section?: NavSectionId;
};

export type NavSection = {
  id: NavSectionId;
  label: string;
  icon: LucideIcon;
  items: NavItem[];
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
  "phone-call": PhoneCall,
  "phone-forwarded": PhoneForwarded,
  "message-square": MessageSquare,
  "check-square": CheckSquare,
  folder: Folder,
  layers: Layers,
  map: LayoutGrid,
  "layout-grid": LayoutGrid,
  "layout-dashboard": LayoutDashboard,
  "hard-hat": HardHat,
  home: Home,
  "rotate-ccw": RotateCcw,
  percent: Percent,
  box: Box,
  bot: Bot,
  store: Store,
  "book-open": BookOpen,
  shield: Shield,
  "list-ordered": ListOrdered,
  chart: ChartNoAxesCombined,
  settings: Settings,
  "clipboard-list": ClipboardList,
  sparkles: Sparkles,
  zap: Zap,
  "key-round": KeyRound,
  blocks: Blocks,
  palette: Palette,
  "circle-dollar": CircleDollarSign,
};

export const NAV_SECTION_META: Record<
  NavSectionId,
  { label: string; icon: LucideIcon }
> = {
  work: { label: NAV_SECTION_LABELS.work, icon: LayoutDashboard },
  crm: { label: NAV_SECTION_LABELS.crm, icon: BriefcaseBusiness },
  ai: { label: NAV_SECTION_LABELS.ai, icon: Bot },
  admin: { label: NAV_SECTION_LABELS.admin, icon: Settings },
};

export function iconForCrm(name?: string | null): LucideIcon {
  if (!name) return Box;
  return ICON_BY_NAME[name] || Box;
}

function leafToItem(leaf: NavLeaf): NavItem {
  return {
    href: leaf.href,
    label: leaf.label,
    icon: ICON_BY_NAME[leaf.icon] || Box,
    permission: leaf.permission,
    section: leaf.section,
  };
}

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
      section: "crm",
    });
  }
  return out;
}

function orgLeaves(crmNavigation?: CrmNavItem[] | null): NavLeaf[] {
  if (crmNavigation && crmNavigation.length > 0) {
    const crmLeaves: NavLeaf[] = crmNavigation
      .filter((item) => Boolean(item.href))
      .map((item) => ({
        href: item.href,
        label: item.label,
        icon: item.icon || "box",
        permission: item.permission || undefined,
        section: "crm" as const,
      }));
    const seen = new Set<string>();
    const out: NavLeaf[] = [];
    for (const item of [...WORK_LEAVES, ...crmLeaves, ...AI_LEAVES, ...ADMIN_LEAVES]) {
      if (seen.has(item.href)) continue;
      seen.add(item.href);
      out.push(item);
    }
    return out;
  }
  return defaultOrgLeaves();
}

/** Flat permission-filtered nav (command palette, tech shell, etc.). */
export function navFor(
  user: OpsUser,
  crmNavigation?: CrmNavItem[] | null,
): NavItem[] {
  if (isTechnicianShell(user)) {
    return filterNavByPermission(user, TECH_NAV);
  }
  return filterNavByPermission(user, orgLeaves(crmNavigation).map(leafToItem));
}

/**
 * Group already-filtered items into sections.
 * Sections are visual only — empty sections are dropped.
 */
export function groupNavIntoSections(items: NavItem[]): NavSection[] {
  return NAV_SECTION_ORDER.map((id) => {
    const meta = NAV_SECTION_META[id];
    return {
      id,
      label: meta.label,
      icon: meta.icon,
      items: items.filter((item) => (item.section || "work") === id),
    };
  }).filter((section) => section.items.length > 0);
}

/**
 * Section-wise nav: filter EACH page by permission, then drop empty sections.
 * Never hide an entire section because one child permission is missing.
 */
export function navSectionsFor(
  user: OpsUser,
  crmNavigation?: CrmNavItem[] | null,
): NavSection[] {
  if (isTechnicianShell(user)) {
    const items = filterNavByPermission(user, TECH_NAV);
    if (!items.length) return [];
    return [
      {
        id: "work",
        label: "Work",
        icon: Briefcase,
        items,
      },
    ];
  }
  const sections = sectionsFromLeaves(user, orgLeaves(crmNavigation));
  return sections.map((section) => ({
    id: section.id,
    label: section.label,
    icon: NAV_SECTION_META[section.id].icon,
    items: section.items.map(leafToItem),
  }));
}

export function sectionContainingPath(
  sections: NavSection[],
  pathname: string,
): NavSectionId | null {
  for (const section of sections) {
    if (section.items.some((item) => isActivePath(pathname, item.href))) {
      return section.id;
    }
  }
  return null;
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

// Re-export leaf catalogs for tests / diagnostics (icons attached in shell).
export { CRM_LEAVES, WORK_LEAVES, AI_LEAVES, ADMIN_LEAVES };
