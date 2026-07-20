import {
  BookOpen,
  Briefcase,
  Calendar,
  CreditCard,
  LayoutDashboard,
  LayoutGrid,
  Mic,
  Phone,
  PhoneForwarded,
  Settings,
  Users,
  Wrench,
  BarChart3,
} from "lucide-react";
import type { OpsUser } from "@/lib/api";

export type NavItem = {
  href: string;
  label: string;
  icon: typeof LayoutGrid;
  roles?: string[];
};

const OPS_NAV: NavItem[] = [
  { href: "/dashboard", label: "Dashboard", icon: LayoutDashboard },
  { href: "/dispatch", label: "Dispatch", icon: LayoutGrid },
  { href: "/customers", label: "Customers", icon: Users },
  { href: "/calls", label: "Calls", icon: Phone },
  { href: "/appointments", label: "Appointments", icon: Calendar },
  { href: "/metrics", label: "Metrics", icon: BarChart3 },
  { href: "/knowledge", label: "Knowledge", icon: BookOpen },
  { href: "/handoff", label: "Handoff", icon: PhoneForwarded },
  { href: "/settings", label: "Settings", icon: Settings, roles: ["admin"] },
  {
    href: "/settings/assistant",
    label: "Assistant",
    icon: Mic,
    roles: ["admin"],
  },
  {
    href: "/settings/billing",
    label: "Billing",
    icon: CreditCard,
    roles: ["admin"],
  },
  { href: "/tech", label: "Tech", icon: Wrench, roles: ["admin"] },
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
  return pathname === href || pathname.startsWith(`${href}/`);
}
