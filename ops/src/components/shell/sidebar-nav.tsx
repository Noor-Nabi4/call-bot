"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { OpsUser } from "@/lib/api";
import { cn } from "@/lib/cn";
import { isActivePath, navFor, type NavItem } from "./nav";

const SECTION_LABELS: Record<NonNullable<NavItem["section"]>, string> = {
  work: "Workspace",
  ai: "AI Voice",
  admin: "Admin",
};

export function SidebarNavigation({
  user,
  collapsed,
}: {
  user: OpsUser;
  collapsed?: boolean;
}) {
  const pathname = usePathname();
  const items = navFor(user);
  const sections: NonNullable<NavItem["section"]>[] = ["work", "ai", "admin"];

  return (
    <nav aria-label="Primary" className="flex flex-1 flex-col gap-4 overflow-y-auto px-2 py-3">
      {sections.map((section) => {
        const sectionItems = items.filter((item) => (item.section || "work") === section);
        if (!sectionItems.length) return null;
        return (
          <div key={section}>
            {!collapsed ? (
              <p className="mb-1.5 px-3 text-[10px] font-semibold tracking-[0.16em] text-[#7f968c] uppercase">
                {SECTION_LABELS[section]}
              </p>
            ) : null}
            <div className="flex flex-col gap-0.5">
              {sectionItems.map((item) => {
                const active = isActivePath(pathname, item.href);
                const Icon = item.icon;
                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    title={item.label}
                    className={cn(
                      "ops-nav-item inline-flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-all duration-200",
                      active
                        ? "bg-[#45d6ac]/18 text-[#f3f8f5] shadow-[inset_0_0_0_1px_rgba(69,214,172,0.25)]"
                        : "text-[#afc2ba] hover:bg-white/10 hover:text-[#f3f8f5]",
                      collapsed && "justify-center px-2",
                    )}
                    aria-current={active ? "page" : undefined}
                  >
                    <Icon
                      className={cn(
                        "size-4 shrink-0 transition-transform duration-200",
                        active ? "text-[#45d6ac] scale-105" : "text-current",
                      )}
                      aria-hidden
                    />
                    {!collapsed ? <span>{item.label}</span> : null}
                  </Link>
                );
              })}
            </div>
          </div>
        );
      })}
    </nav>
  );
}
