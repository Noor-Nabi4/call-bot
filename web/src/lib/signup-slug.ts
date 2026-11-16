/** Signup Workspace ID (tenant slug) helpers — format only; uniqueness is server-side. */

export const SIGNUP_SLUG_PATTERN = /^[a-z0-9]+(?:-[a-z0-9]+)*$/;
export const SIGNUP_SLUG_MIN = 2;
export const SIGNUP_SLUG_MAX = 64;
/** Debounce before availability API — avoid per-keystroke requests. */
export const SIGNUP_SLUG_CHECK_DEBOUNCE_MS = 450;

export function slugifyBusinessName(value: string): string {
  const cleaned = value
    .trim()
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .slice(0, SIGNUP_SLUG_MAX)
    .replace(/^-+|-+$/g, "");
  return cleaned.length >= SIGNUP_SLUG_MIN ? cleaned : "workspace";
}

export function normalizeSignupSlug(value: string): string {
  return value.trim().toLowerCase();
}

export function isSignupSlugFormatValid(slug: string): boolean {
  const cleaned = normalizeSignupSlug(slug);
  return (
    cleaned.length >= SIGNUP_SLUG_MIN &&
    cleaned.length <= SIGNUP_SLUG_MAX &&
    SIGNUP_SLUG_PATTERN.test(cleaned)
  );
}
