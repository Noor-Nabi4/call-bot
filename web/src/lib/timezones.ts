/** Timezone helpers — prefer backend `/geo/catalog` for the full IANA list. */

export type TimezoneOption = {
  value: string;
  label: string;
};

/** Minimal fallback when the geo catalog has not loaded yet. */
export const TIMEZONE_OPTIONS: TimezoneOption[] = [
  { value: "UTC", label: "UTC (GMT)" },
];

export function resolveInitialTimezone(): string {
  const detected =
    typeof Intl !== "undefined"
      ? Intl.DateTimeFormat().resolvedOptions().timeZone
      : "UTC";
  return detected || "UTC";
}

/** Options plus browser/current timezone if it isn’t already listed. */
export function timezoneOptionsForSelect(
  current: string,
  catalog: TimezoneOption[] = TIMEZONE_OPTIONS,
): TimezoneOption[] {
  const base = catalog.length ? catalog : TIMEZONE_OPTIONS;
  if (!current || base.some((z) => z.value === current)) {
    return base;
  }
  return [
    { value: current, label: current.replace(/_/g, " ") },
    ...base,
  ];
}
