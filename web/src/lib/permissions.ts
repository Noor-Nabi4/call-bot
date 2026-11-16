import type { OpsUser } from "@/types";

export type EffectivePermission = {
  key: string;
  resource: string;
  action: string;
  scope: string;
};

export type EffectiveRole = {
  id: string;
  name: string;
  system: boolean;
};

/** UX-only permission check. Backend RBAC remains authoritative. */
export function hasPermission(
  user: Pick<OpsUser, "permissions"> | null | undefined,
  key: string,
): boolean {
  if (!user?.permissions?.length) return false;
  return user.permissions.some((p) => p.key === key);
}

export function hasAnyPermission(
  user: Pick<OpsUser, "permissions"> | null | undefined,
  keys: string[],
): boolean {
  return keys.some((key) => hasPermission(user, key));
}

export function hasAllPermissions(
  user: Pick<OpsUser, "permissions"> | null | undefined,
  keys: string[],
): boolean {
  return keys.every((key) => hasPermission(user, key));
}

/**
 * Technician-oriented chrome (layout/display only).
 * Prefer RBAC role names from /me; fall back to assigned-scope jobs without analytics.
 */
export function isTechnicianShell(
  user: Pick<OpsUser, "permissions" | "roles"> | null | undefined,
): boolean {
  if (!user) return false;
  const roleNames = user.roles?.map((r) => r.name) ?? [];
  if (roleNames.includes("Technician")) {
    const ops = new Set([
      "Owner",
      "Admin",
      "Manager",
      "Dispatcher",
      "CSR",
      "Accountant",
    ]);
    if (!roleNames.some((n) => ops.has(n))) return true;
  }
  const jobs = user.permissions?.find((p) => p.key === "jobs.read");
  if (
    jobs?.scope === "ASSIGNED" &&
    !hasPermission(user, "analytics.read") &&
    !hasPermission(user, "organization.read")
  ) {
    return true;
  }
  return false;
}

export function permissionScope(
  user: Pick<OpsUser, "permissions"> | null | undefined,
  key: string,
): string | null {
  const match = user?.permissions?.find((p) => p.key === key);
  return match?.scope ?? null;
}

/** Filter nav items by effective permission (UX only). */
export function filterNavByPermission<T extends { permission?: string }>(
  user: Pick<OpsUser, "permissions"> | null | undefined,
  items: T[],
): T[] {
  return items.filter(
    (item) => !item.permission || hasPermission(user, item.permission),
  );
}
