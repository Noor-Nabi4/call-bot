/** Thin geo helpers — catalogs load from the backend `/geo` APIs. */

export type GeoOption = { value: string; label: string };

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
