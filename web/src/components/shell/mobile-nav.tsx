"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { X } from "lucide-react";
import type { OpsUser } from "@/lib/api";
import { cn } from "@/lib/cn";
import { isActivePath, navFor } from "./nav";
import { TenantSwitcher } from "./tenant-switcher";

export function MobileNavDrawer({
  user,
  open,
  onClose,
}: {
  user: OpsUser;
  open: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();
  const items = navFor(user);
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-40 lg:hidden" role="dialog" aria-modal>
      <button
        type="button"
        className="absolute inset-0 bg-text-primary/20"
        aria-label="Close menu"
        onClick={onClose}
      />
      <aside className="ops-sidebar absolute top-0 bottom-0 left-0 flex w-64 flex-col border-r border-white/10 shadow-[var(--shadow-elevated)]">
        <div className="flex items-center justify-between border-b border-white/10 px-3 py-3">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img
            src="/branding/logo-dark.svg"
            alt="VoxPilot"
            width={120}
            height={26}
            className="h-6 w-auto"
          />
          <button
            type="button"
            className="rounded-[10px] p-1.5 text-hero-muted hover:bg-white/10 hover:text-white"
            aria-label="Close"
            onClick={onClose}
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="px-3 pt-3">
          <TenantSwitcher user={user} tone="dark" />
        </div>
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          {items.map((item) => {
            const Icon = item.icon;
            const active = isActivePath(pathname, item.href);
            return (
              <Link
                key={item.href}
                href={item.href}
                onClick={onClose}
                className={cn(
                  "mb-0.5 flex items-center gap-2 rounded-[10px] px-2.5 py-2.5 text-sm font-medium",
                  active
                    ? "bg-teal-bright/18 text-white"
                    : "text-hero-muted hover:bg-white/10 hover:text-white",
                )}
              >
                <Icon
                  className={cn(
                    "size-4",
                    active ? "text-teal-bright" : "text-current",
                  )}
                  aria-hidden
                />
                {item.label}
              </Link>
            );
          })}
        </nav>
      </aside>
    </div>
  );
}
