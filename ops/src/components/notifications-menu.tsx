"use client";

import Link from "next/link";
import { Bell, RefreshCw } from "lucide-react";
import { useEffect, useId, useRef, useState } from "react";
import type { AttentionItem } from "@/lib/attention";
import { cn } from "@/lib/cn";
import { notifications as copy } from "@/lib/copy";
import {
  formatUpdatedAgo,
  useAttentionFeed,
} from "@/lib/use-attention-feed";

function toneClass(tone: AttentionItem["tone"]): string {
  if (tone === "urgent") return "border-l-danger";
  if (tone === "warn") return "border-l-warn";
  return "border-l-brand";
}

export function NotificationsMenu() {
  const [open, setOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());
  const ref = useRef<HTMLDivElement>(null);
  const menuId = useId();
  const feed = useAttentionFeed(open);
  const hasItems = feed.summary.length > 0 || feed.jobAlerts.length > 0;

  useEffect(() => {
    if (!open) return;
    const id = window.setInterval(() => setNow(Date.now()), 1000);
    return () => window.clearInterval(id);
  }, [open]);

  useEffect(() => {
    if (!open) return;
    void feed.refresh({ soft: true });
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
    // Intentionally omit feed.refresh identity churn — open gate is enough.
    // eslint-disable-next-line react-hooks/exhaustive-deps -- open-driven
  }, [open]);

  const updatedLabel = formatUpdatedAgo(feed.lastUpdatedAt, now);

  return (
    <div className="relative" ref={ref}>
      <button
        type="button"
        className={cn(
          "relative rounded-md border border-border p-2 text-text-muted transition-colors duration-150 hover:bg-surface-muted hover:text-text-primary",
          feed.badge > 0 && "text-text-primary",
        )}
        aria-label={
          feed.badge > 0
            ? `Notifications, ${feed.badge} need attention`
            : "Notifications"
        }
        aria-expanded={open}
        aria-haspopup="dialog"
        aria-controls={menuId}
        aria-live="polite"
        onClick={() => setOpen((v) => !v)}
      >
        <Bell
          className={cn("size-4", feed.badgePulse && "attention-bell-ring")}
          aria-hidden
        />
        {feed.badge > 0 ? (
          <span
            className={cn(
              "absolute -top-1.5 -right-1.5 inline-flex min-w-4 items-center justify-center rounded-full bg-danger px-1 text-[10px] font-semibold leading-4 text-white tabular-nums transition-transform",
              feed.badgePulse && "attention-badge-pulse",
            )}
          >
            {feed.badge > 99 ? "99+" : feed.badge}
          </span>
        ) : null}
      </button>

      {open ? (
        <div
          id={menuId}
          role="dialog"
          aria-label={copy.title}
          className="absolute right-0 z-40 mt-1.5 w-[min(100vw-2rem,22rem)] overflow-hidden rounded-xl border border-border bg-surface shadow-[var(--shadow-elevated)] animate-[fade-in_160ms_ease-out]"
        >
          <div className="flex items-center justify-between gap-2 border-b border-border px-3 py-2.5">
            <div className="min-w-0">
              <p className="font-heading text-sm font-semibold text-text-primary">
                {copy.title}
              </p>
              <p className="truncate text-[11px] text-text-muted">
                {feed.badge > 0
                  ? `${feed.badge} job${feed.badge === 1 ? "" : "s"} need action`
                  : copy.liveIdle}
                {updatedLabel ? ` · ${updatedLabel}` : ""}
              </p>
            </div>
            <button
              type="button"
              className="inline-flex shrink-0 items-center gap-1 rounded-md border border-border px-2 py-1 text-[11px] font-medium text-text-secondary hover:bg-surface-muted disabled:opacity-50"
              onClick={() => void feed.refresh({ soft: true })}
              disabled={feed.refreshing}
            >
              <RefreshCw
                className={cn("size-3", feed.refreshing && "animate-spin")}
                aria-hidden
              />
              {copy.refresh}
            </button>
          </div>

          <div className="max-h-[min(70vh,24rem)] overflow-y-auto">
            {feed.loading && !hasItems ? (
              <p className="px-3 py-6 text-center text-sm text-text-muted">
                Loading…
              </p>
            ) : null}

            {feed.error ? (
              <p className="px-3 py-4 text-sm text-danger" role="alert">
                {feed.error}
              </p>
            ) : null}

            {!feed.loading && !feed.error && !hasItems ? (
              <div className="px-3 py-6 text-center">
                <p className="text-sm font-medium text-text-primary">
                  {copy.empty}
                </p>
                <p className="mt-1 text-xs text-text-muted">{copy.emptyHint}</p>
              </div>
            ) : null}

            {feed.summary.length > 0 ? (
              <section className="border-b border-border px-2 py-2">
                <p className="px-1.5 pb-1 text-[10px] font-semibold tracking-wide text-text-muted uppercase">
                  {copy.summary}
                </p>
                <ul className="m-0 list-none space-y-1 p-0">
                  {feed.summary.map((item) => (
                    <li key={item.id} className="attention-row-enter">
                      <Link
                        href={item.href}
                        onClick={() => setOpen(false)}
                        className={cn(
                          "flex items-start justify-between gap-2 rounded-md border-l-2 px-2.5 py-2 text-left transition-colors hover:bg-surface-muted",
                          toneClass(item.tone),
                        )}
                      >
                        <div className="min-w-0">
                          <p className="text-sm font-medium text-text-primary">
                            {item.title}
                          </p>
                          <p className="mt-0.5 text-xs text-text-muted">
                            {item.explanation}
                          </p>
                        </div>
                        <span className="shrink-0 font-heading text-sm font-semibold tabular-nums text-brand">
                          {item.count}
                        </span>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}

            {feed.jobAlerts.length > 0 ? (
              <section className="px-2 py-2">
                <p className="px-1.5 pb-1 text-[10px] font-semibold tracking-wide text-text-muted uppercase">
                  {copy.jobs}
                </p>
                <ul className="m-0 list-none space-y-1 p-0">
                  {feed.jobAlerts.map((item) => (
                    <li key={item.id} className="attention-row-enter">
                      <Link
                        href={item.href}
                        onClick={() => setOpen(false)}
                        className={cn(
                          "block rounded-md border-l-2 px-2.5 py-2 transition-colors hover:bg-surface-muted",
                          toneClass(item.tone),
                        )}
                      >
                        <p className="text-sm font-medium text-text-primary">
                          {item.title}
                        </p>
                        <p className="mt-0.5 text-xs text-text-muted">
                          {item.explanation}
                        </p>
                      </Link>
                    </li>
                  ))}
                </ul>
              </section>
            ) : null}
          </div>

          <div className="border-t border-border px-3 py-2">
            <Link
              href="/dispatch"
              onClick={() => setOpen(false)}
              className="text-xs font-medium text-brand hover:underline"
            >
              {copy.viewDispatch}
            </Link>
          </div>
        </div>
      ) : null}
    </div>
  );
}
