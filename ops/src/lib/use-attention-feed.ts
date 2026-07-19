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
import { notifications as copy } from "@/lib/copy";
import { safeUserError } from "@/lib/safe-error";

const POLL_HIDDEN_MS = 60_000;
const POLL_IDLE_MS = 20_000;
const POLL_ACTIVE_MS = 8_000;
const POLL_OPEN_MS = 4_000;

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
  if (open) return POLL_OPEN_MS;
  if (typeof document !== "undefined" && document.hasFocus()) {
    return POLL_ACTIVE_MS;
  }
  return POLL_IDLE_MS;
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
    void refresh();
  }, [refresh]);

  // Adaptive polling — faster while open / focused, slower when idle/hidden.
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
      if (document.visibilityState === "visible") bump();
      else if (timer) {
        clearTimeout(timer);
        schedule();
      }
    };

    window.addEventListener("focus", bump);
    document.addEventListener("visibilitychange", onVisibility);
    window.addEventListener(ATTENTION_REFRESH_EVENT, bump);

    return () => {
      cancelled = true;
      if (timer) clearTimeout(timer);
      window.removeEventListener("focus", bump);
      document.removeEventListener("visibilitychange", onVisibility);
      window.removeEventListener(ATTENTION_REFRESH_EVENT, bump);
    };
  }, [open, refresh]);

  // Route changes often follow job edits — soft refresh.
  useEffect(() => {
    void refresh({ soft: true });
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
