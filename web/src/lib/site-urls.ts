/** Same-origin paths after marketing + ops merged into one Next.js app. */

export function opsUrl(): string {
  return "/login";
}

export function opsLoginUrl(): string {
  return "/login";
}

export function opsPlaygroundUrl(): string {
  return "/playground";
}

export type FooterHrefKind = "playground" | "ops" | "login" | "pricing";

export function resolveFooterHref(kind: FooterHrefKind): string {
  if (kind === "playground") return opsPlaygroundUrl();
  if (kind === "ops") return "/login";
  if (kind === "pricing") return "/pricing";
  return opsLoginUrl();
}
