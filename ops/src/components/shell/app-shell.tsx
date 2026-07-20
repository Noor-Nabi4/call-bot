"use client";

import Link from "next/link";
import { Menu, PanelLeftClose, PanelLeftOpen, Search } from "lucide-react";
import {
  useEffect,
  useState,
  useSyncExternalStore,
  type CSSProperties,
  type ReactNode,
} from "react";
import type { OpsUser } from "@/lib/api";
import { NotificationsMenu } from "@/components/notifications-menu";
import { CommandSearch } from "./command-search";
import { MobileNavDrawer } from "./mobile-nav";
import { SidebarNavigation } from "./sidebar-nav";
import { TechBottomNav } from "./tech-bottom-nav";
import { TenantSwitcher } from "./tenant-switcher";
import { UserMenu } from "./user-menu";

type Branding = {
  product_name?: string | null;
  logo_url?: string | null;
  primary_color?: string | null;
  accent_color?: string | null;
};

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

const SIDEBAR_COLLAPSED_KEY = "ops-sidebar-collapsed";
const SIDEBAR_COLLAPSED_EVENT = "ops-sidebar-collapsed-change";

function subscribeSidebarCollapsed(onStoreChange: () => void) {
  window.addEventListener("storage", onStoreChange);
  window.addEventListener(SIDEBAR_COLLAPSED_EVENT, onStoreChange);
  return () => {
    window.removeEventListener("storage", onStoreChange);
    window.removeEventListener(SIDEBAR_COLLAPSED_EVENT, onStoreChange);
  };
}

function getSidebarCollapsedSnapshot() {
  try {
    return localStorage.getItem(SIDEBAR_COLLAPSED_KEY) === "1";
  } catch {
    return false;
  }
}

function getSidebarCollapsedServerSnapshot() {
  return false;
}

function setSidebarCollapsedPreference(collapsed: boolean) {
  try {
    localStorage.setItem(SIDEBAR_COLLAPSED_KEY, collapsed ? "1" : "0");
  } catch {
    /* ignore */
  }
  window.dispatchEvent(new Event(SIDEBAR_COLLAPSED_EVENT));
}

export function AppShell({
  user,
  children,
}: {
  user: OpsUser;
  children: ReactNode;
}) {
  const [searchOpen, setSearchOpen] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const sidebarCollapsed = useSyncExternalStore(
    subscribeSidebarCollapsed,
    getSidebarCollapsedSnapshot,
    getSidebarCollapsedServerSnapshot,
  );
  const [branding, setBranding] = useState<Branding | null>(null);
  const isTech = user.role === "technician";
  const productName = branding?.product_name?.trim() || "VoxPilot";

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (
        e.key === "/" &&
        !(e.target instanceof HTMLInputElement) &&
        !(e.target instanceof HTMLTextAreaElement)
      ) {
        e.preventDefault();
        setSearchOpen(true);
      }
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, []);

  useEffect(() => {
    if (user.role !== "admin" && user.role !== "dispatcher") return;
    let cancelled = false;
    fetch(`${API}/api/admin/branding`, { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) return null;
        return res.json() as Promise<{ branding: Branding }>;
      })
      .then((data) => {
        if (!cancelled && data?.branding) setBranding(data.branding);
      })
      .catch(() => {
        /* branding is optional chrome */
      });
    return () => {
      cancelled = true;
    };
  }, [user.role]);

  function toggleSidebarCollapsed() {
    setSidebarCollapsedPreference(!sidebarCollapsed);
  }

  const brandStyle = {
    ...(branding?.primary_color
      ? {
          ["--ops-accent" as string]: branding.primary_color,
          ["--color-brand" as string]: branding.primary_color,
        }
      : {}),
    ...(branding?.accent_color
      ? { ["--ops-accent-hover" as string]: branding.accent_color }
      : {}),
  } as CSSProperties;

  if (isTech) {
    return (
      <div
        className="ops-shell-atmosphere min-h-screen text-text-primary"
        style={brandStyle}
      >
        <div className="ops-shell-inner">
          <header className="sticky top-0 z-30 border-b border-border bg-paper/85 backdrop-blur-xl">
            <div className="mx-auto flex h-14 max-w-lg items-center justify-between gap-3 px-4">
              <div>
                <p className="text-[10px] font-medium tracking-[0.14em] text-text-muted uppercase">
                  {productName}
                </p>
                <p className="font-display text-sm font-semibold tracking-tight">
                  {user.tenant_name}
                </p>
              </div>
              <UserMenu user={user} />
            </div>
          </header>
          <main className="mx-auto max-w-lg px-4 py-4 pb-24">{children}</main>
          <TechBottomNav user={user} />
        </div>
      </div>
    );
  }

  return (
    <div
      className="ops-shell-atmosphere min-h-screen text-text-primary"
      style={brandStyle}
    >
      <div className="ops-shell-inner lg:flex">
        <aside
          className="ops-sidebar sticky top-0 hidden h-screen shrink-0 flex-col border-r border-white/10 lg:flex"
          data-collapsed={sidebarCollapsed ? "true" : "false"}
        >
          <div
            className={
              sidebarCollapsed
                ? "flex flex-col items-center px-2 pt-4"
                : "px-3 pt-4"
            }
          >
            <Link
              href="/dashboard"
              className="block text-white"
              title={productName}
            >
              {sidebarCollapsed ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src="/branding/favicon.svg"
                  alt={productName}
                  width={28}
                  height={28}
                  className="size-7 object-contain"
                />
              ) : branding?.logo_url ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={branding.logo_url}
                  alt={productName}
                  className="mb-2 h-8 max-w-[160px] object-contain"
                />
              ) : (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src="/branding/logo-dark.svg"
                  alt={productName}
                  width={148}
                  height={32}
                  className="mb-2 h-7 w-auto"
                />
              )}
            </Link>
            {!sidebarCollapsed ? (
              <p className="mt-1 text-[11px] tracking-[0.08em] text-hero-muted uppercase">
                Operations
              </p>
            ) : null}
            <div className={sidebarCollapsed ? "mt-3 w-full" : "mt-4"}>
              <TenantSwitcher
                user={user}
                tone="dark"
                collapsed={sidebarCollapsed}
              />
            </div>
          </div>

          <SidebarNavigation user={user} collapsed={sidebarCollapsed} />

          <div
            className={
              sidebarCollapsed
                ? "mt-auto border-t border-white/10 p-2"
                : "mt-auto border-t border-white/10 p-3"
            }
          >
            <button
              type="button"
              onClick={toggleSidebarCollapsed}
              className={
                sidebarCollapsed
                  ? "flex w-full items-center justify-center rounded-[10px] p-2 text-hero-muted transition-colors hover:bg-white/10 hover:text-white"
                  : "flex w-full items-center gap-2 rounded-[10px] px-3 py-2 text-sm font-medium text-hero-muted transition-colors hover:bg-white/10 hover:text-white"
              }
              aria-label={
                sidebarCollapsed ? "Expand sidebar" : "Collapse sidebar"
              }
              aria-expanded={!sidebarCollapsed}
            >
              {sidebarCollapsed ? (
                <PanelLeftOpen className="size-4" aria-hidden />
              ) : (
                <>
                  <PanelLeftClose className="size-4 shrink-0" aria-hidden />
                  <span>Collapse</span>
                </>
              )}
            </button>
          </div>
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border bg-surface/80 px-4 backdrop-blur-xl sm:px-6">
            <button
              type="button"
              className="rounded-[10px] border border-border p-2 text-text-secondary lg:hidden"
              aria-label="Open menu"
              onClick={() => setMobileOpen(true)}
            >
              <Menu className="size-4" />
            </button>
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              className="hidden items-center gap-2 rounded-[10px] border border-border bg-surface px-2.5 py-1.5 text-xs text-text-muted transition-colors duration-150 hover:bg-surface-muted sm:inline-flex"
              aria-label="Open search"
            >
              <Search className="size-3.5" aria-hidden />
              <span>Search</span>
              <kbd className="rounded border border-border bg-fog px-1 font-mono text-[10px]">
                /
              </kbd>
            </button>
            <div className="ml-auto flex items-center gap-1.5">
              <NotificationsMenu />
              <UserMenu user={user} />
            </div>
          </header>

          <main className="mx-auto w-full max-w-[1600px] flex-1 px-4 py-5 sm:px-6 sm:py-8">
            {children}
          </main>
        </div>

        <MobileNavDrawer
          user={user}
          open={mobileOpen}
          onClose={() => setMobileOpen(false)}
        />
        <CommandSearch
          open={searchOpen}
          onClose={() => setSearchOpen(false)}
          user={user}
        />
      </div>
    </div>
  );
}
