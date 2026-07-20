"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { OpsUser } from "@/lib/api";
import { cn } from "@/lib/cn";
import { isActivePath, navFor } from "./nav";

export function SidebarNavigation({
  user,
  collapsed,
}: {
  user: OpsUser;
  collapsed?: boolean;
}) {
  const pathname = usePathname();
  const items = navFor(user);

  return (
    <nav aria-label="Primary" className="flex flex-1 flex-col gap-0.5 px-2 py-3">
      {items.map((item) => {
        const active = isActivePath(pathname, item.href);
        const Icon = item.icon;
        return (
          <Link
            key={item.href}
            href={item.href}
            title={item.label}
            className={cn(
              "inline-flex items-center gap-2.5 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150",
              active
                ? "bg-[#45d6ac]/18 text-[#f3f8f5]"
                : "text-[#afc2ba] hover:bg-white/10 hover:text-[#f3f8f5]",
              collapsed && "justify-center px-2",
            )}
            aria-current={active ? "page" : undefined}
          >
            <Icon
              className={cn(
                "size-4 shrink-0",
                active ? "text-[#45d6ac]" : "text-current",
              )}
              aria-hidden
            />
            {!collapsed ? <span>{item.label}</span> : null}
          </Link>
        );
      })}
    </nav>
  );
}
