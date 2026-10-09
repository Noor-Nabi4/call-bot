/** Shared fetch wrapper for platform ops APIs (cookie session). */

import { safeUserError } from "@/lib/safe-error";
import { errors } from "@/lib/ops-copy";
import { ApiError } from "./api-error";

export { ApiError, isAssignmentConflict, isBookingConflict } from "./api-error";

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
  return handleApiResponse<T>(res);
}

/**
 * Multipart upload helper — omits the JSON Content-Type header so the
 * browser sets the multipart boundary itself. Shared by any API module that
 * uploads files (product images, job attachments, etc.).
 */
export async function apiMultipart<T>(
  path: string,
  form: FormData,
  init?: Omit<RequestInit, "body">
): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    method: "POST",
    ...init,
    credentials: "include",
    body: form,
  });
  return handleApiResponse<T>(res);
}

async function handleApiResponse<T>(res: Response): Promise<T> {
  if (!res.ok) {
    let message: string = errors.generic;
    let code: string | undefined;
    let reason: string | undefined;
    try {
      const body = await res.json();
      const detail = body?.detail;
      if (typeof detail === "string") message = detail;
      else if (detail?.message) message = detail.message;
      if (typeof detail === "object" && detail?.code) code = detail.code;
      if (typeof detail === "object" && detail?.reason) {
        reason = String(detail.reason);
      }
    } catch {
      /* ignore */
    }
    if (code === "subscription_required" && typeof window !== "undefined") {
      const pathNow = window.location.pathname;
      if (!pathNow.startsWith("/settings/billing")) {
        window.location.assign("/settings/billing");
      }
    }
    if (code === "ONBOARDING_REQUIRED" && typeof window !== "undefined") {
      const pathNow = window.location.pathname;
      if (!pathNow.startsWith("/onboarding") && !pathNow.startsWith("/phones")) {
        window.location.assign(
          reason === "phone_required"
            ? "/phones?from=onboarding"
            : "/onboarding",
        );
      }
    }
    throw new ApiError(safeUserError(message, errors.generic), res.status, code);
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
  "NEW",
  "SCHEDULED",
  "DISPATCHED",
  "IN_PROGRESS",
  "COMPLETED",
  "CANCELLED",
] as const;
