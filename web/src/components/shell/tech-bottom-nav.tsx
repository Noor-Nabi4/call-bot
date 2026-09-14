"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import type { OpsUser } from "@/lib/api";
import { cn } from "@/lib/cn";
import { isActivePath, navFor } from "./nav";

export function TechBottomNav({ user }: { user: OpsUser }) {
  const pathname = usePathname();
  const items = navFor(user);
  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-30 border-t border-border bg-surface px-2 py-1.5 lg:hidden"
      aria-label="Technician"
    >
      <div className="mx-auto flex max-w-lg items-center justify-around">
        {items.map((item) => {
          const active = isActivePath(pathname, item.href);
          const Icon = item.icon;
          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex min-w-[4.5rem] flex-col items-center gap-0.5 rounded-[10px] px-3 py-2 text-[11px] font-medium",
                active ? "text-brand" : "text-text-muted",
              )}
            >
              <Icon className="size-5" aria-hidden />
              {item.label}
            </Link>
          );
        })}
      </div>
    </nav>
  );
}
