"use client";

import type { OpsUser } from "@/lib/api";
import { cn } from "@/lib/cn";

export function TenantSwitcher({
  user,
  tone = "light",
}: {
  user: OpsUser;
  tone?: "light" | "dark";
}) {
  const dark = tone === "dark";
  return (
    <div
      className={cn(
        "flex items-center gap-2 rounded-md border px-2.5 py-1.5",
        dark
          ? "border-white/15 bg-white/5"
          : "border-border bg-surface",
      )}
      title="Active business"
    >
      <span
        className={cn(
          "size-1.5 shrink-0 rounded-full",
          dark ? "bg-[#45d6ac]" : "bg-brand",
        )}
        aria-hidden
      />
      <div className="min-w-0">
        <p
          className={cn(
            "truncate text-sm font-medium",
            dark ? "text-[#f3f8f5]" : "text-text-primary",
          )}
        >
          {user.tenant_name}
        </p>
      </div>
    </div>
  );
}
