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
  Users,
  Wrench,
  BarChart3,
  Zap,
} from "lucide-react";
import type { OpsUser } from "@/lib/api";

export type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutGrid;
  roles?: string[];
  section?: "work" | "ai" | "admin";
};

const OPS_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard, section: "work" },
  { href: "/dispatch", label: "Dispatch", icon: LayoutGrid, section: "work" },
  { href: "/customers", label: "Customers", icon: Users, section: "work" },
  { href: "/live", label: "Live", icon: PhoneCall, section: "work" },
  { href: "/supervisor", label: "Supervisor", icon: Shield, section: "work" },
  { href: "/queue", label: "Queue", icon: ListOrdered, section: "work" },
  { href: "/calls", label: "Calls", icon: Phone, section: "work" },
  { href: "/appointments", label: "Appointments", icon: Calendar, section: "work" },
  { href: "/metrics", label: "Metrics", icon: BarChart3, section: "work" },
  { href: "/agents", label: "Agents", icon: Bot, roles: ["admin"], section: "ai" },
  { href: "/marketplace", label: "Marketplace", icon: Store, roles: ["admin"], section: "ai" },
  { href: "/phones", label: "Phones", icon: Phone, roles: ["admin"], section: "ai" },
  { href: "/knowledge", label: "Knowledge", icon: BookOpen, section: "ai" },
  { href: "/handoff", label: "Handoff", icon: PhoneForwarded, section: "ai" },
  { href: "/settings", label: "Settings", icon: Settings, roles: ["admin"], section: "admin" },
  {
    href: "/settings/team",
    label: "Team",
    icon: Users,
    roles: ["admin"],
    section: "admin",
  },
  {
    href: "/settings/billing",
    label: "Billing",
    icon: CreditCard,
    roles: ["admin"],
    section: "admin",
  },
  {
    href: "/settings/automations",
    label: "Automations",
    icon: Zap,
    roles: ["admin"],
    section: "admin",
  },
  { href: "/tech", label: "Tech", icon: Wrench, roles: ["admin"], section: "admin" },
];

const TECH_NAV: NavItem[] = [
  { href: "/tech", label: "Jobs", icon: Briefcase },
];

export function navFor(user: OpsUser): NavItem[] {
  if (user.role === "technician") return TECH_NAV;
  return OPS_NAV.filter(
    (item) => !item.roles || item.roles.includes(user.role),
  );
}

export function isActivePath(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  if (href === "/dispatch") {
    return pathname === "/dispatch" || pathname === "/board";
  }
  if (href === "/agents") {
    return pathname === "/agents" || pathname.startsWith("/agents/");
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}
