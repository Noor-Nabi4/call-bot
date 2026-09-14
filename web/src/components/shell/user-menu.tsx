"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { ChevronDown, LogOut, UserRound } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import { logout, type OpsUser } from "@/lib/api";
import { cn } from "@/lib/cn";

function userInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

export function UserMenu({ user }: { user: OpsUser }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const initials = userInitials(user.name) || "?";

  useEffect(() => {
    if (!open) return;
    const onDoc = (e: MouseEvent) => {
      if (!ref.current?.contains(e.target as Node)) setOpen(false);
    };
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setOpen(false);
    };
    document.addEventListener("mousedown", onDoc);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("mousedown", onDoc);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  async function onLogout() {
    await logout().catch(() => undefined);
    router.replace("/login");
  }

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className={cn(
          "inline-flex items-center gap-2 rounded-full py-1 pr-1.5 pl-1 text-left transition-colors duration-150",
          "hover:bg-fog focus-visible:outline-brand",
          open && "bg-fog",
        )}
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={menuId}
        aria-label={`Account menu for ${user.name}`}
        onClick={() => setOpen((v) => !v)}
      >
        <span
          className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-hero text-[11px] font-semibold tracking-wide text-teal-bright"
          aria-hidden
        >
          {initials}
        </span>
        <span className="hidden min-w-0 sm:block">
          <span className="block max-w-[8.5rem] truncate text-sm font-semibold leading-tight text-ink">
            {user.name}
          </span>
          <span className="block max-w-[8.5rem] truncate text-[11px] leading-tight text-text-muted capitalize">
            {user.role}
          </span>
        </span>
        <ChevronDown
          className={cn(
            "mr-0.5 hidden size-3.5 shrink-0 text-text-muted transition-transform duration-150 sm:block",
            open && "rotate-180",
          )}
          aria-hidden
        />
      </button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 z-40 mt-2 w-64 overflow-hidden rounded-xl border border-border bg-surface shadow-[var(--shadow-elevated)]"
        >
          <div className="border-b border-border bg-fog/60 px-3 py-3">
            <div className="flex items-center gap-2.5">
              <span
                className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-hero text-xs font-semibold text-teal-bright"
                aria-hidden
              >
                {initials}
              </span>
              <div className="min-w-0">
                <p className="truncate text-sm font-semibold text-ink">
                  {user.name}
                </p>
                <p className="truncate text-xs text-text-muted">{user.email}</p>
              </div>
            </div>
          </div>
          <div className="py-1">
            <Link
              href="/profile"
              role="menuitem"
              className="flex w-full items-center gap-2.5 px-3 py-2.5 text-sm text-text-primary transition-colors hover:bg-fog"
              onClick={() => setOpen(false)}
            >
              <UserRound className="size-4 text-brand" aria-hidden />
              Edit profile
            </Link>
            <button
              type="button"
              role="menuitem"
              className="flex w-full items-center gap-2.5 px-3 py-2.5 text-sm text-text-primary transition-colors hover:bg-fog"
              onClick={onLogout}
            >
              <LogOut className="size-4 text-text-muted" aria-hidden />
              Log out
            </button>
          </div>
        </div>
      ) : null}
    </div>
  );
}
