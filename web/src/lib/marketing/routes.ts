/** Canonical public marketing routes for sitemap, nav, and internal linking. */

export const PUBLIC_MARKETING_ROUTES = [
  { path: "/", priority: 1, changeFrequency: "weekly" as const },
  { path: "/ai-voice-agents", priority: 0.95, changeFrequency: "weekly" as const },
  { path: "/ai-receptionist", priority: 0.95, changeFrequency: "weekly" as const },
  { path: "/pricing", priority: 0.9, changeFrequency: "weekly" as const },
  { path: "/industries", priority: 0.85, changeFrequency: "weekly" as const },
  { path: "/use-cases", priority: 0.85, changeFrequency: "weekly" as const },
  { path: "/blog", priority: 0.7, changeFrequency: "weekly" as const },
  { path: "/signup", priority: 0.6, changeFrequency: "monthly" as const },
] as const;

/** Authenticated / internal paths that must not be indexed. */
export const ROBOTS_DISALLOW = [
  "/api/",
  "/login",
  "/dashboard",
  "/agents",
  "/appointments",
  "/board",
  "/calls",
  "/customers",
  "/dispatch",
  "/handoff",
  "/jobs",
  "/knowledge",
  "/live",
  "/marketplace",
  "/metrics",
  "/phones",
  "/playground",
  "/profile",
  "/queue",
  "/settings",
  "/supervisor",
  "/tech",
] as const;
