/** Thin geo helpers — catalogs load from the backend `/geo` APIs. */

export type GeoOption = { value: string; label: string };

export type CountryCatalogItem = {
  key: string;
  name: string;
  default_currency_code?: string | null;
};

export type CurrencyCatalogItem = {
  key: string;
  name: string;
  symbol?: string | null;
};

export function normalizeCountryCode(raw: string | null | undefined): string {
  const value = (raw || "").trim();
  if (!value) return "";
  if (value.length === 2) return value.toUpperCase();
  return "";
}

export function normalizeCurrencyCode(raw: string | null | undefined): string {
  const value = (raw || "").trim().toUpperCase();
  return value.slice(0, 3);
}

/** Regional-indicator flag emoji from an ISO 3166-1 alpha-2 code. */
export function countryFlagEmoji(code: string | null | undefined): string {
  const cc = normalizeCountryCode(code);
  if (cc.length !== 2) return "";
  const A = 0x1f1e6;
  const base = "A".charCodeAt(0);
  return String.fromCodePoint(
    A + (cc.charCodeAt(0) - base),
    A + (cc.charCodeAt(1) - base),
  );
}

export function currencySymbol(
  code: string | null | undefined,
  fallbackSymbol?: string | null,
): string {
  const cleaned = normalizeCurrencyCode(code);
  if (!cleaned) return "";
  if (fallbackSymbol?.trim()) return fallbackSymbol.trim();
  try {
    const parts = new Intl.NumberFormat("en", {
      style: "currency",
      currency: cleaned,
      currencyDisplay: "narrowSymbol",
    }).formatToParts(0);
    const sym = parts.find((p) => p.type === "currency")?.value;
    return sym || cleaned;
  } catch {
    return cleaned;
  }
}

export function formatCountryLabel(
  code: string,
  name: string,
): string {
  const flag = countryFlagEmoji(code);
  return flag ? `${flag} ${name}` : name;
}

export function formatCurrencyLabel(
  code: string,
  name: string,
  symbol?: string | null,
): string {
  const sym = currencySymbol(code, symbol);
  if (sym && sym !== code) {
    return `${sym} ${code} — ${name}`;
  }
  return `${code} — ${name}`;
}

/** Keep a saved custom value selectable even if it is not in the catalog. */
export function optionsWithCurrent(
  options: GeoOption[],
  current: string | null | undefined,
): GeoOption[] {
  const value = (current || "").trim();
  if (!value) return options;
  if (options.some((o) => o.value === value)) return options;
  return [{ value, label: value }, ...options];
}

export function catalogToOptions(
  items: Array<{ key: string; name: string }> | null | undefined,
): GeoOption[] {
  if (!items?.length) return [];
  return items.map((item) => ({ value: item.key, label: item.name }));
}

export function catalogToCountryOptions(
  items: CountryCatalogItem[] | null | undefined,
): GeoOption[] {
  if (!items?.length) return [];
  return items.map((item) => ({
    value: item.key,
    label: formatCountryLabel(item.key, item.name),
  }));
}

export function catalogToCurrencyOptions(
  items: CurrencyCatalogItem[] | null | undefined,
): GeoOption[] {
  if (!items?.length) return [];
  return items.map((item) => ({
    value: item.key,
    label: formatCurrencyLabel(item.key, item.name, item.symbol),
  }));
}

export function defaultCurrencyForCountry(
  countryCode: string | null | undefined,
  countries: CountryCatalogItem[] | null | undefined,
): string {
  const code = normalizeCountryCode(countryCode);
  if (!code || !countries?.length) return "";
  const match = countries.find((c) => c.key === code);
  return normalizeCurrencyCode(match?.default_currency_code || "");
}

/** Browser IANA timezone (e.g. Asia/Karachi). */
export function resolveBrowserTimezone(): string {
  try {
    const detected =
      typeof Intl !== "undefined"
        ? Intl.DateTimeFormat().resolvedOptions().timeZone
        : "";
    return (detected || "").trim() || "UTC";
  } catch {
    return "UTC";
  }
}

/** Common IANA zone → country when locale has no region (e.g. en + Asia/Karachi). */
const TIMEZONE_COUNTRY_HINTS: Record<string, string> = {
  "Asia/Karachi": "PK",
  "Asia/Kolkata": "IN",
  "Asia/Calcutta": "IN",
  "Asia/Dhaka": "BD",
  "Asia/Dubai": "AE",
  "Asia/Riyadh": "SA",
  "Asia/Singapore": "SG",
  "Asia/Tokyo": "JP",
  "Asia/Shanghai": "CN",
  "Asia/Hong_Kong": "HK",
  "Europe/London": "GB",
  "Europe/Paris": "FR",
  "Europe/Berlin": "DE",
  "Australia/Sydney": "AU",
  "Pacific/Auckland": "NZ",
  "America/New_York": "US",
  "America/Chicago": "US",
  "America/Denver": "US",
  "America/Los_Angeles": "US",
  "America/Toronto": "CA",
  "America/Vancouver": "CA",
  "America/Sao_Paulo": "BR",
};

function pickAllowedCountry(
  raw: string | null | undefined,
  allowed: Set<string> | null,
): string {
  const code = normalizeCountryCode(raw);
  if (!code) return "";
  if (allowed && !allowed.has(code)) return "";
  return code;
}

export function countryFromTimezone(
  timezone: string | null | undefined,
): string {
  const tz = (timezone || "").trim();
  if (!tz) return "";
  return TIMEZONE_COUNTRY_HINTS[tz] || "";
}

/**
 * Best-effort ISO country from timezone first, then browser locale.
 * Prefer wall-clock zone over language (en-US + Asia/Karachi → PK).
 * Does not use GPS; no permission prompt.
 */
export function resolveBrowserCountryCode(
  countries?: CountryCatalogItem[] | null,
  timezone?: string | null,
): string {
  const allowed = countries?.length
    ? new Set(countries.map((c) => c.key.toUpperCase()))
    : null;

  const tz =
    (timezone || "").trim() || resolveBrowserTimezone();
  const fromTz = pickAllowedCountry(countryFromTimezone(tz), allowed);
  if (fromTz) return fromTz;

  const candidates: string[] = [];
  try {
    const language =
      typeof navigator !== "undefined" ? navigator.language || "" : "";
    if (language && typeof Intl !== "undefined" && "Locale" in Intl) {
      const locale = new Intl.Locale(language);
      if (locale.region) candidates.push(locale.region);
      const maximized =
        typeof locale.maximize === "function" ? locale.maximize() : null;
      if (maximized?.region) candidates.push(maximized.region);
    }
    const parts = language.split(/[-_]/);
    if (parts.length >= 2 && parts[1] && /^[A-Za-z]{2}$/.test(parts[1])) {
      candidates.push(parts[1]);
    }
  } catch {
    /* ignore */
  }

  for (const raw of candidates) {
    const code = pickAllowedCountry(raw, allowed);
    if (code) return code;
  }
  return "";
}

export type LiveGeoDefaults = {
  country: string;
  currency: string;
  timezone: string;
};

/** Live browser defaults for empty onboarding/signup geo fields. */
export function resolveLiveGeoDefaults(
  countries?: CountryCatalogItem[] | null,
  timezone?: string | null,
): LiveGeoDefaults {
  const tz = (timezone || "").trim() || resolveBrowserTimezone();
  const country = resolveBrowserCountryCode(countries, tz);
  const currency = defaultCurrencyForCountry(country, countries) || "USD";
  return {
    country,
    currency,
    timezone: tz,
  };
}

/**
 * Fill blank geo fields from the browser without overwriting saved values.
 *
 * Once country/currency/timezone are persisted, refresh must keep them even if
 * the browser locale/timezone would suggest a different country (e.g. en-US
 * language with Asia/Karachi clock).
 */
export function applyLiveGeoDefaults<
  T extends {
    country?: string | null;
    currency?: string | null;
    timezone?: string | null;
  },
>(
  profile: T,
  countries?: CountryCatalogItem[] | null,
): T {
  const savedTimezone = (profile.timezone || "").trim();
  const savedCountry = normalizeCountryCode(profile.country);
  const savedCurrency = normalizeCurrencyCode(profile.currency);
  const live = resolveLiveGeoDefaults(countries, savedTimezone || null);

  // Only fill missing timezone; never replace an explicit saved value (incl. UTC).
  const timezone = savedTimezone || live.timezone || "UTC";

  // Never overwrite a saved country on refresh — US+USD is a valid saved profile.
  const country = savedCountry || live.country || countryFromTimezone(timezone) || "";

  let currency = savedCurrency;
  if (!currency) {
    currency =
      (country
        ? defaultCurrencyForCountry(country, countries)
        : null) ||
      live.currency ||
      "USD";
  }

  return {
    ...profile,
    country: country || profile.country || null,
    currency,
    timezone,
  };
}
