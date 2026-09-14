/** Shared fetch wrapper for platform ops APIs (cookie session). */

import { safeUserError } from "@/lib/safe-error";
import { errors } from "@/lib/ops-copy";

export const API_BASE =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      ...(init?.headers || {}),
    },
  });
  if (!res.ok) {
    let message: string = errors.generic;
    let code: string | undefined;
    try {
      const body = await res.json();
      const detail = body?.detail;
      if (typeof detail === "string") message = detail;
      else if (detail?.message) message = detail.message;
      if (typeof detail === "object" && detail?.code) code = detail.code;
    } catch {
      /* ignore */
    }
    if (code === "subscription_required" && typeof window !== "undefined") {
      const pathNow = window.location.pathname;
      if (!pathNow.startsWith("/settings/billing")) {
        window.location.assign("/settings/billing");
      }
    }
    throw new Error(safeUserError(message, errors.generic));
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export function formatWhen(iso?: string | null) {
  if (!iso) return "—";
  try {
    return new Date(iso).toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}

export const STATUS_ORDER = [
  "new",
  "scheduled",
  "dispatched",
  "in_progress",
  "completed",
  "canceled",
] as const;
