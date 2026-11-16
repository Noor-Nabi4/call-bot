"use client";

import { useEffect, useState } from "react";
import type { OpsUser } from "@/lib/api";
import { hasPermission } from "@/lib/permissions";

const API =
  process.env.NEXT_PUBLIC_PLATFORM_API_URL?.replace(/\/$/, "") ||
  "http://localhost:8000";

export type CrmNavItem = {
  key: string;
  label: string;
  href: string;
  icon?: string;
  permission?: string | null;
  display_order?: number;
  category?: string;
};

export type EffectiveCrmConfiguration = {
  navigation: CrmNavItem[];
  enabled_modules: { key: string; name: string; enabled: boolean }[];
  field_types: string[];
  custom_objects: { id: string; object_key: string; name: string }[];
  setup_completed?: boolean;
};

export function useCrmConfiguration(user: OpsUser | null | undefined) {
  const [config, setConfig] = useState<EffectiveCrmConfiguration | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!user) {
      setConfig(null);
      return;
    }
    if (!hasPermission(user, "organization.read")) {
      setConfig(null);
      return;
    }
    let cancelled = false;
    setLoading(true);
    setError(null);
    fetch(`${API}/api/admin/crm/configuration`, { credentials: "include" })
      .then(async (res) => {
        if (!res.ok) throw new Error("Failed to load CRM configuration");
        return res.json();
      })
      .then((body) => {
        if (cancelled) return;
        setConfig(body.configuration as EffectiveCrmConfiguration);
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : "CRM config error");
        setConfig(null);
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [user]);

  return { config, loading, error };
}
