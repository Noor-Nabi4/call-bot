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

  useEffect(() => {
    let cancelled = false;
    me()
      .then(({ user: u }) => {
        if (cancelled) return;
        if (opts?.roles && !opts.roles.includes(u.role)) {
          router.replace(u.role === "technician" ? "/tech" : "/board");
          return;
        }
        setUser(u);
      })
      .catch(() => {
        if (!cancelled) router.replace(opts?.redirectTo || "/login");
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [router, opts?.redirectTo, opts?.roles?.join(",")]);

  return { user, loading };
}
