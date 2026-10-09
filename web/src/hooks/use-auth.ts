"use client";

import { useCallback, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { me, type OpsUser } from "@/lib/api";
import {
  isOnboardingComplete,
  needsPhoneSetup,
  ONBOARDING_PATH,
  PHONES_ONBOARDING_PATH,
} from "@/lib/onboarding";
import {
  hasAllPermissions,
  hasAnyPermission,
  hasPermission,
  isTechnicianShell,
} from "@/lib/permissions";

export function useAuth(opts?: {
  /** Require a single effective permission (UX gate). */
  permission?: string;
  /** Require any of these permissions. */
  permissions?: string[];
  /** Require all of these permissions. */
  requireAll?: string[];
  /**
   * @deprecated Legacy JWT role gate — do not use for authorization.
   * Prefer `permission` / `permissions`. Kept temporarily for display migration.
   */
  roles?: string[];
  redirectTo?: string;
  /**
   * When false (default), incomplete onboarding redirects to /onboarding.
   * Set true for onboarding wizard, billing checkout, and auth-adjacent pages.
   */
  allowIncompleteOnboarding?: boolean;
}) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState<OpsUser | null>(null);
  const [loading, setLoading] = useState(true);
  const [forbidden, setForbidden] = useState(false);
  const redirectTo = opts?.redirectTo;
  const permission = opts?.permission;
  const permissionsKey = opts?.permissions?.join(",") ?? "";
  const requireAllKey = opts?.requireAll?.join(",") ?? "";
  const allowIncompleteOnboarding = Boolean(opts?.allowIncompleteOnboarding);

  const load = useCallback(async () => {
    const anyOf = permissionsKey ? permissionsKey.split(",") : [];
    const allOf = requireAllKey ? requireAllKey.split(",") : [];
    const { user: u } = await me();

    let allowed = true;
    if (permission && !hasPermission(u, permission)) allowed = false;
    if (anyOf.length > 0 && !hasAnyPermission(u, anyOf)) allowed = false;
    if (allOf.length > 0 && !hasAllPermissions(u, allOf)) allowed = false;

    if (!allowed) {
      setForbidden(true);
      setUser(u);
      return u;
    }

    setForbidden(false);
    setUser(u);
    return u;
  }, [permission, permissionsKey, requireAllKey]);

  useEffect(() => {
    let cancelled = false;
    queueMicrotask(() => {
      if (cancelled) return;
      setLoading(true);
      load()
        .then((u) => {
          if (cancelled || !u) return;
          if (!allowIncompleteOnboarding && !isOnboardingComplete(u)) {
            const onPhones = pathname.startsWith("/phones");
            const onOnboarding = pathname.startsWith(ONBOARDING_PATH);
            if (!onPhones && !onOnboarding) {
              router.replace(
                needsPhoneSetup(u) ? PHONES_ONBOARDING_PATH : ONBOARDING_PATH,
              );
            }
          }
        })
        .catch(() => {
          if (!cancelled) router.replace(redirectTo || "/login");
        })
        .finally(() => {
          if (!cancelled) setLoading(false);
        });
    });
    return () => {
      cancelled = true;
    };
  }, [
    load,
    router,
    redirectTo,
    allowIncompleteOnboarding,
    pathname,
  ]);

  const refresh = useCallback(async (): Promise<OpsUser | null> => {
    try {
      const u = await load();
      if (u && !allowIncompleteOnboarding && !isOnboardingComplete(u)) {
        const onPhones = pathname.startsWith("/phones");
        const onOnboarding = pathname.startsWith(ONBOARDING_PATH);
        if (!onPhones && !onOnboarding) {
          router.replace(
            needsPhoneSetup(u) ? PHONES_ONBOARDING_PATH : ONBOARDING_PATH,
          );
        }
      }
      return u;
    } catch {
      router.replace(redirectTo || "/login");
      return null;
    }
  }, [
    load,
    router,
    redirectTo,
    allowIncompleteOnboarding,
    pathname,
  ]);

  return {
    user,
    loading,
    forbidden,
    refresh,
    can: (key: string) => hasPermission(user, key),
    isTechShell: isTechnicianShell(user),
  };
}
