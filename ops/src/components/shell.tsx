"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  BookOpen,
  Briefcase,
  Calendar,
  ChevronDown,
  LayoutDashboard,
  LayoutGrid,
  LogOut,
  Menu,
  Mic,
  Phone,
  PhoneForwarded,
  Search,
  Settings,
  UserRound,
  Users,
  Wrench,
  X,
  BarChart3,
} from "lucide-react";
import {
  useCallback,
  useEffect,
  useId,
  useRef,
  useState,
  type ReactNode,
} from "react";
import { logout, type OpsUser } from "@/lib/api";
import { cn } from "@/lib/cn";
import { NotificationsMenu } from "@/components/notifications-menu";
import { StatusPill } from "@/components/ui/status-pill";

export { StatusPill };

type NavItem = {
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

function isActivePath(pathname: string, href: string): boolean {
  if (href === "/dashboard") return pathname === "/dashboard";
  if (href === "/dispatch") {
    return pathname === "/dispatch" || pathname === "/board";
  }
  return pathname === href || pathname.startsWith(`${href}/`);
}

function TenantSwitcher({
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

function userInitials(name: string): string {
  return name
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() || "")
    .join("");
}

function UserMenu({ user }: { user: OpsUser }) {
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
          className="inline-flex size-8 shrink-0 items-center justify-center rounded-full bg-[#0f221c] text-[11px] font-semibold tracking-wide text-[#45d6ac]"
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
                className="inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-[#0f221c] text-xs font-semibold text-[#45d6ac]"
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

function SidebarNavigation({
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

function MobileNavDrawer({
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
          <p className="font-heading text-sm font-semibold tracking-tight text-[#f3f8f5]">
            Call Bot
          </p>
          <button
            type="button"
            className="rounded-md p-1.5 text-[#afc2ba] hover:bg-white/10 hover:text-[#f3f8f5]"
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
                  "mb-0.5 flex items-center gap-2 rounded-md px-2.5 py-2.5 text-sm font-medium",
                  active
                    ? "bg-[#45d6ac]/18 text-[#f3f8f5]"
                    : "text-[#afc2ba] hover:bg-white/10 hover:text-[#f3f8f5]",
                )}
              >
                <Icon
                  className={cn(
                    "size-4",
                    active ? "text-[#45d6ac]" : "text-current",
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

function TechBottomNav({ user }: { user: OpsUser }) {
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

function CommandSearch({
  open,
  onClose,
  user,
}: {
  open: boolean;
  onClose: () => void;
  user: OpsUser;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [q, setQ] = useState("");
  const router = useRouter();

  useEffect(() => {
    if (!open) return;
    const id = requestAnimationFrame(() => inputRef.current?.focus());
    return () => cancelAnimationFrame(id);
  }, [open]);

  const handleClose = useCallback(() => {
    setQ("");
    onClose();
  }, [onClose]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") handleClose();
    };
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [open, handleClose]);

  if (!open) return null;

  const destinations = navFor(user)
    .map((i) => ({ label: i.label, href: i.href }))
    .filter((d) => d.label.toLowerCase().includes(q.toLowerCase()));

  return (
    <div className="fixed inset-0 z-50 grid place-items-start justify-center px-4 pt-[12vh]">
      <button
        type="button"
        className="absolute inset-0 bg-text-primary/25"
        aria-label="Close search"
        onClick={handleClose}
      />
      <div
        role="dialog"
        aria-label="Search"
        className="relative z-10 w-full max-w-lg overflow-hidden rounded-xl border border-border bg-surface shadow-[var(--shadow-elevated)]"
      >
        <div className="flex items-center gap-2 border-b border-border px-3">
          <Search className="size-4 text-text-muted" aria-hidden />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => setQ(e.target.value)}
            placeholder="Go to…"
            className="h-11 flex-1 bg-transparent text-sm outline-none"
          />
        </div>
        <ul className="max-h-64 overflow-y-auto py-1">
          {destinations.map((d) => (
            <li key={d.href}>
              <button
                type="button"
                className="flex w-full px-3 py-2 text-left text-sm hover:bg-surface-muted"
                onClick={() => {
                  handleClose();
                  router.push(d.href);
                }}
              >
                {d.label}
              </button>
            </li>
          ))}
          {destinations.length === 0 ? (
            <li className="px-3 py-4 text-sm text-text-muted">No matches</li>
          ) : null}
        </ul>
      </div>
    </div>
  );
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
  const isTech = user.role === "technician";

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

  if (isTech) {
    return (
      <div className="ops-shell-atmosphere min-h-screen text-text-primary">
        <div className="ops-shell-inner">
          <header className="sticky top-0 z-30 border-b border-border bg-paper/85 backdrop-blur-xl">
            <div className="mx-auto flex h-14 max-w-lg items-center justify-between gap-3 px-4">
              <div>
                <p className="text-[10px] font-medium tracking-[0.14em] text-text-muted uppercase">
                  Call Bot
                </p>
                <p className="font-heading text-sm font-semibold tracking-tight">
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
    <div className="ops-shell-atmosphere min-h-screen text-text-primary">
      <div className="ops-shell-inner lg:flex">
        <aside className="ops-sidebar sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-white/10 p-4 lg:flex">
          <div className="px-3">
            <Link href="/dashboard" className="block text-[#f3f8f5]">
              <p className="font-heading text-xl font-semibold tracking-[-0.03em]">
                Call Bot
              </p>
            </Link>
            <p className="mt-1 text-[11px] text-[#afc2ba]">Operations</p>
            <div className="mt-4">
              <TenantSwitcher user={user} tone="dark" />
            </div>
          </div>
          <SidebarNavigation user={user} />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border bg-paper/85 px-4 backdrop-blur-xl sm:px-6">
            <button
              type="button"
              className="rounded-md border border-border p-2 text-text-secondary lg:hidden"
              aria-label="Open menu"
              onClick={() => setMobileOpen(true)}
            >
              <Menu className="size-4" />
            </button>
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              className="hidden items-center gap-2 rounded-md border border-border bg-surface px-2.5 py-1.5 text-xs text-text-muted transition-colors duration-150 hover:bg-surface-muted sm:inline-flex"
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
