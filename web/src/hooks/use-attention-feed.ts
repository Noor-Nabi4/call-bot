"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { usePathname } from "next/navigation";
import {
  getHandoffSettings,
  listJobs,
  listTechnicians,
  type HandoffSettings,
  type Job,
  type Technician,
} from "@/lib/api";
import {
  attentionBadgeCount,
  buildAttentionItems,
  buildJobAlerts,
  type AttentionItem,
} from "@/lib/attention";
import {
  ATTENTION_REFRESH_EVENT,
} from "@/lib/attention-bus";
import { notifications as copy } from "@/lib/ops-copy";
import { safeUserError } from "@/lib/safe-error";

// Badge feed is shell-wide — keep closed-tab polling slow so billing/settings
// pages are not flooded with jobs/technicians/handoff traffic.
const POLL_HIDDEN_MS = 120_000;
const POLL_CLOSED_MS = 60_000;
const POLL_OPEN_MS = 12_000;

export type AttentionFeed = {
  summary: AttentionItem[];
  jobAlerts: AttentionItem[];
  badge: number;
  loading: boolean;
  refreshing: boolean;
  error: string | null;
  lastUpdatedAt: number | null;
  badgePulse: boolean;
  refresh: (opts?: { soft?: boolean }) => Promise<void>;
};

function pollIntervalMs(open: boolean): number {
  if (typeof document !== "undefined" && document.visibilityState === "hidden") {
    return POLL_HIDDEN_MS;
  }
  return open ? POLL_OPEN_MS : POLL_CLOSED_MS;
}

export function useAttentionFeed(open: boolean): AttentionFeed {
  const pathname = usePathname();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [techs, setTechs] = useState<Technician[]>([]);
  const [handoff, setHandoff] = useState<HandoffSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [lastUpdatedAt, setLastUpdatedAt] = useState<number | null>(null);
  const [badgePulse, setBadgePulse] = useState(false);
  const prevBadge = useRef(0);
  const inFlight = useRef(false);

  const refresh = useCallback(async (opts?: { soft?: boolean }) => {
    if (inFlight.current) return;
    inFlight.current = true;
    if (!opts?.soft) setLoading(true);
    else setRefreshing(true);
    try {
      const [j, t, h] = await Promise.all([
        listJobs(),
        listTechnicians(),
        getHandoffSettings().catch(() => null),
      ]);
      setJobs(j.jobs);
      setTechs(t.technicians);
      setHandoff(h?.settings ?? null);
      setError(null);
      setLastUpdatedAt(Date.now());
    } catch (err) {
      setError(safeUserError(err, copy.loadFailed));
    } finally {
      setLoading(false);
      setRefreshing(false);
      inFlight.current = false;
    }
  }, []);

  useEffect(() => {
    queueMicrotask(() => {
      void refresh();
    });
  }, [refresh]);

  // Poll slowly while the bell is closed; faster only while the menu is open.
  // Do not refetch on every route change — that flooded unrelated pages.
  useEffect(() => {
    let timer: ReturnType<typeof setTimeout> | null = null;
    let cancelled = false;

    const schedule = () => {
      if (cancelled) return;
      timer = setTimeout(() => {
        void refresh({ soft: true }).finally(() => {
          schedule();
        });
      }, pollIntervalMs(open));
    };

    schedule();

    const bump = () => {
      if (timer) clearTimeout(timer);
      void refresh({ soft: true });
      schedule();
    };

    const onVisibility = () => {
      if (timer) clearTimeout(timer);
      if (document.visibilityState === "visible") {
        // Tab back: one soft refresh, then resume slow/open cadence.
        void refresh({ soft: true }).finally(() => schedule());
      } else {
        schedule();
      }
    };

    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener(ATTENTION_REFRESH_EVENT, bump);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener(ATTENTION_REFRESH_EVENT, bump);
    };
  }, [open, refresh]);

  // Soft refresh only when navigating onto ops surfaces that edit attention data.
  useEffect(() => {
    if (!pathname) return;
    const opsSurface =
      pathname.startsWith("/jobs") ||
      pathname.startsWith("/crm/jobs") ||
      pathname.startsWith("/dispatch") ||
      pathname.startsWith("/crm/dispatch") ||
      pathname.startsWith("/queue") ||
      pathname.startsWith("/handoff") ||
      pathname.startsWith("/crm/handoffs") ||
      pathname.startsWith("/tech");
    if (!opsSurface) return;
    queueMicrotask(() => {
      void refresh({ soft: true });
    });
  }, [pathname, refresh]);

  const summary = buildAttentionItems({
    jobs,
    technicians: techs,
    handoff,
  });
  const jobAlerts = buildJobAlerts(jobs);
  const badge = attentionBadgeCount(summary);

  useEffect(() => {
    if (badge > prevBadge.current) {
      setBadgePulse(true);
      const id = window.setTimeout(() => setBadgePulse(false), 1200);
      prevBadge.current = badge;
      return () => window.clearTimeout(id);
    }
    prevBadge.current = badge;
    return undefined;
  }, [badge]);

  return {
    summary,
    jobAlerts,
    badge,
    loading,
    refreshing,
    error,
    lastUpdatedAt,
    badgePulse,
    refresh,
  };
}

export function formatUpdatedAgo(lastUpdatedAt: number | null, now: number): string {
  if (!lastUpdatedAt) return "";
  const seconds = Math.max(0, Math.floor((now - lastUpdatedAt) / 1000));
  if (seconds < 5) return "Updated just now";
  if (seconds < 60) return `Updated ${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `Updated ${minutes}m ago`;
  return `Updated ${Math.floor(minutes / 60)}h ago`;
}
