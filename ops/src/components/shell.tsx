"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Bell,
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

function TenantSwitcher({ user }: { user: OpsUser }) {
  return (
    <div
      className="flex items-center gap-2 rounded-[10px] border border-border bg-surface px-2.5 py-1.5"
      title="Active business"
    >
      <span className="size-1.5 shrink-0 rounded-full bg-brand" aria-hidden />
      <div className="min-w-0">
        <p className="truncate text-sm font-medium text-text-primary">
          {user.tenant_name}
        </p>
      </div>
    </div>
  );
}

function UserMenu({ user }: { user: OpsUser }) {
  const router = useRouter();
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();

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
        className="inline-flex items-center gap-2 rounded-[10px] border border-border bg-surface px-2 py-1.5 text-sm transition-colors duration-150 hover:bg-surface-muted"
        aria-expanded={open}
        aria-haspopup="menu"
        aria-controls={menuId}
        onClick={() => setOpen((v) => !v)}
      >
        <span className="hidden max-w-[9rem] truncate text-text-primary lg:inline">
          {user.name}
        </span>
        <span className="rounded-md bg-surface-muted px-1.5 py-0.5 text-[10px] font-medium tracking-wide text-text-secondary uppercase">
          {user.role}
        </span>
        <ChevronDown className="size-3.5 text-text-muted" aria-hidden />
      </button>
      {open ? (
        <div
          id={menuId}
          role="menu"
          className="absolute right-0 z-40 mt-1.5 w-56 rounded-xl border border-border bg-surface py-1 shadow-[var(--shadow-elevated)]"
        >
          <div className="border-b border-border px-3 py-2">
            <p className="truncate text-sm font-medium">{user.name}</p>
            <p className="truncate text-xs text-text-muted">{user.email}</p>
          </div>
          <button
            type="button"
            role="menuitem"
            className="flex w-full items-center gap-2 px-3 py-2 text-sm text-text-primary hover:bg-surface-muted"
            onClick={onLogout}
          >
            <LogOut className="size-4" aria-hidden />
            Log out
          </button>
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
              "inline-flex items-center gap-2.5 rounded-lg px-3 py-2 text-sm font-medium transition-colors duration-150",
              active
                ? "bg-brand/15 text-text-primary"
                : "text-text-muted hover:bg-white/5 hover:text-text-primary",
              collapsed && "justify-center px-2",
            )}
            aria-current={active ? "page" : undefined}
          >
            <Icon className="size-4 shrink-0" aria-hidden />
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
      <aside className="absolute top-0 bottom-0 left-0 flex w-64 flex-col border-r border-border bg-surface shadow-[var(--shadow-elevated)]">
        <div className="flex items-center justify-between border-b border-border px-3 py-3">
          <p className="text-sm font-semibold">Call Bot</p>
          <button
            type="button"
            className="rounded-[10px] p-1.5 text-text-muted hover:bg-surface-muted"
            aria-label="Close"
            onClick={onClose}
          >
            <X className="size-4" />
          </button>
        </div>
        <div className="px-3 pt-3">
          <TenantSwitcher user={user} />
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
                    ? "bg-brand-soft text-brand"
                    : "text-text-primary hover:bg-surface-muted",
                )}
              >
                <Icon className="size-4" aria-hidden />
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
          <header className="sticky top-0 z-30 border-b border-border bg-background/80 backdrop-blur-xl">
            <div className="mx-auto flex h-14 max-w-lg items-center justify-between gap-3 px-4">
              <div>
                <p className="text-[10px] font-medium tracking-[0.14em] text-text-muted uppercase">
                  Call Bot
                </p>
                <p className="font-heading text-sm font-semibold">{user.tenant_name}</p>
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
        <aside className="sticky top-0 hidden h-screen w-60 shrink-0 flex-col border-r border-border bg-background/80 p-4 backdrop-blur-xl lg:flex">
          <div className="px-3">
            <Link href="/dashboard" className="block text-text-primary">
              <p className="font-heading text-base font-semibold tracking-tight">
                Call Bot
              </p>
            </Link>
            <p className="mt-1 text-[11px] text-text-muted">Operations</p>
            <div className="mt-4">
              <TenantSwitcher user={user} />
            </div>
          </div>
          <SidebarNavigation user={user} />
        </aside>

        <div className="flex min-w-0 flex-1 flex-col">
          <header className="sticky top-0 z-30 flex h-14 items-center gap-2 border-b border-border bg-background/80 px-4 backdrop-blur-xl sm:px-6">
            <button
              type="button"
              className="rounded-lg border border-border p-2 text-text-secondary lg:hidden"
              aria-label="Open menu"
              onClick={() => setMobileOpen(true)}
            >
              <Menu className="size-4" />
            </button>
            <button
              type="button"
              onClick={() => setSearchOpen(true)}
              className="hidden items-center gap-2 rounded-lg border border-border bg-surface/60 px-2.5 py-1.5 text-xs text-text-muted transition-colors duration-150 hover:bg-surface-muted sm:inline-flex"
              aria-label="Open search"
            >
              <Search className="size-3.5" aria-hidden />
              <span>Search</span>
              <kbd className="rounded border border-border bg-surface px-1 font-mono text-[10px]">
                /
              </kbd>
            </button>
            <div className="ml-auto flex items-center gap-1.5">
              <button
                type="button"
                className="rounded-lg border border-border p-2 text-text-muted transition-colors duration-150 hover:bg-surface-muted hover:text-text-primary"
                aria-label="Notifications"
                title="No unread notifications"
              >
                <Bell className="size-4" />
              </button>
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
