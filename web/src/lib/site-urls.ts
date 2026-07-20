/** Resolved public URLs for marketing CTAs and cross-app links. */

export function playgroundUrl(): string {
  return (
    process.env.NEXT_PUBLIC_PLAYGROUND_URL?.replace(/\/$/, "") ||
    "http://localhost:3000"
  );
}

export function opsUrl(): string {
  return (
    process.env.NEXT_PUBLIC_OPS_URL?.replace(/\/$/, "") ||
    "http://localhost:3001"
  );
}

export function opsLoginUrl(): string {
  return `${opsUrl()}/login`;
}

export type FooterHrefKind = "playground" | "ops" | "login" | "pricing";

export function resolveFooterHref(kind: FooterHrefKind): string {
  if (kind === "playground") return playgroundUrl();
  if (kind === "ops") return opsUrl();
  if (kind === "pricing") return "/#pricing";
  return opsLoginUrl();
}
