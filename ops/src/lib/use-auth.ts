"use client";

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { me, type OpsUser } from "@/lib/api";

export function useAuth(opts?: {
  roles?: string[];
  redirectTo?: string;
}) {
  const router = useRouter();
  const [user, setUser] = useState<OpsUser | null>(null);
  const [loading, setLoading] = useState(true);
  const redirectTo = opts?.redirectTo;
  const rolesKey = opts?.roles?.join(",") ?? "";

  const load = useCallback(async () => {
    const allowedRoles = rolesKey ? rolesKey.split(",") : undefined;
    const { user: u } = await me();
    if (allowedRoles && !allowedRoles.includes(u.role)) {
      router.replace(u.role === "technician" ? "/tech" : "/dashboard");
      return null;
    }
    setUser(u);
    return u;
  }, [router, rolesKey]);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    load()
      .catch(() => {
        if (!cancelled) router.replace(redirectTo || "/login");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [load, router, redirectTo]);

  const refresh = useCallback(async () => {
    try {
      await load();
    } catch {
      router.replace(redirectTo || "/login");
    }
  }, [load, router, redirectTo]);

  return { user, loading, refresh };
}
