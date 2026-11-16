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
