"use client";

import { useEffect, useState } from "react";
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

  useEffect(() => {
    let cancelled = false;
    const allowedRoles = rolesKey ? rolesKey.split(",") : undefined;
    me()
      .then(({ user: u }) => {
        if (cancelled) return;
        if (allowedRoles && !allowedRoles.includes(u.role)) {
          router.replace(u.role === "technician" ? "/tech" : "/dashboard");
          return;
        }
        setUser(u);
      })
      .catch(() => {
        if (!cancelled) router.replace(redirectTo || "/login");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [router, redirectTo, rolesKey]);

  return { user, loading };
}
