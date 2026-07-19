"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { logout, type OpsUser } from "@/lib/api";

export function AppShell({
  user,
  children,
}: {
  user: OpsUser;
  children: React.ReactNode;
}) {
  const router = useRouter();
  const isTech = user.role === "technician";

  async function onLogout() {
    await logout().catch(() => undefined);
    router.replace("/login");
  }

  return (
    <div className="min-h-screen">
      <header className="border-b border-line bg-panel px-4 py-3">
        <div className="mx-auto flex max-w-6xl items-center justify-between gap-4">
          <div>
            <p className="text-xs uppercase tracking-[0.14em] text-ink-muted">
              Call Bot Ops
            </p>
            <h1 className="text-lg font-semibold">{user.tenant_name}</h1>
          </div>
          <nav className="flex items-center gap-3 text-sm">
            {!isTech && (
              <>
                <Link href="/board" className="font-medium">
                  Board
                </Link>
                <Link href="/customers" className="font-medium">
                  Customers
                </Link>
                <Link href="/calls" className="font-medium">
                  Calls
                </Link>
                <Link href="/appointments" className="font-medium">
                  Appts
                </Link>
                <Link href="/metrics" className="font-medium">
                  Metrics
                </Link>
                <Link href="/knowledge" className="font-medium">
                  Knowledge
                </Link>
                <Link href="/handoff" className="font-medium">
                  Handoff
                </Link>
                {user.role === "admin" && (
                  <Link href="/settings" className="font-medium">
                    Settings
                  </Link>
                )}
              </>
            )}
            {(isTech || user.role === "admin") && (
              <Link href="/tech" className="font-medium">
                Tech
              </Link>
            )}
            <span className="text-ink-muted">
              {user.name} · {user.role}
            </span>
            <button
              type="button"
              onClick={onLogout}
              className="rounded border border-line px-2 py-1 text-ink"
            >
              Log out
            </button>
          </nav>
        </div>
      </header>
      <main className="mx-auto max-w-6xl px-4 py-6">{children}</main>
    </div>
  );
}

export function StatusPill({ status }: { status: string }) {
  const tones: Record<string, string> = {
    new: "bg-surface text-ink",
    scheduled: "bg-accent-soft text-accent",
    dispatched: "bg-warn-soft text-warn",
    in_progress: "bg-warn-soft text-warn",
    completed: "bg-accent-soft text-accent",
    canceled: "bg-danger-soft text-danger",
  };
  return (
    <span className={`status-pill ${tones[status] || "bg-surface text-ink"}`}>
      {status.replace("_", " ")}
    </span>
  );
}
