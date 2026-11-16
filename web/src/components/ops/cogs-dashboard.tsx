"use client";

/**
 * Platform-internal COGS UI is not mounted for organization users.
 * Organization Owners use /settings/usage. Former /settings/cogs redirects there.
 * Platform COGS APIs require require_platform_operator — never org Owner sessions.
 */
export function CogsDashboard() {
  return (
    <div className="rounded-[var(--radius-lg)] border border-border p-6 text-sm text-text-muted">
      Platform COGS is not available in the organization app. Use Usage under
      Settings for consumption and plan limits.
    </div>
  );
}
