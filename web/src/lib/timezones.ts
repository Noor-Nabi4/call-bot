/** Common IANA timezones for signup (field-service / US-first). */

export type TimezoneOption = {
  value: string;
  label: string;
};

export const TIMEZONE_OPTIONS: TimezoneOption[] = [
  { value: "America/New_York", label: "Eastern Time (New York)" },
  { value: "America/Chicago", label: "Central Time (Chicago)" },
  { value: "America/Denver", label: "Mountain Time (Denver)" },
  { value: "America/Phoenix", label: "Arizona (Phoenix)" },
  { value: "America/Los_Angeles", label: "Pacific Time (Los Angeles)" },
  { value: "America/Anchorage", label: "Alaska (Anchorage)" },
  { value: "Pacific/Honolulu", label: "Hawaii (Honolulu)" },
  { value: "America/Toronto", label: "Eastern Time (Toronto)" },
  { value: "America/Winnipeg", label: "Central Time (Winnipeg)" },
  { value: "America/Edmonton", label: "Mountain Time (Edmonton)" },
  { value: "America/Vancouver", label: "Pacific Time (Vancouver)" },
  { value: "America/Mexico_City", label: "Mexico City" },
  { value: "UTC", label: "UTC" },
  { value: "Europe/London", label: "London" },
  { value: "Europe/Paris", label: "Paris / Berlin (CET)" },
  { value: "Asia/Dubai", label: "Dubai" },
  { value: "Asia/Karachi", label: "Karachi" },
  { value: "Asia/Kolkata", label: "India (Kolkata)" },
  { value: "Asia/Singapore", label: "Singapore" },
  { value: "Australia/Sydney", label: "Sydney" },
];

export function resolveInitialTimezone(): string {
  const detected =
    typeof Intl !== "undefined"
      ? Intl.DateTimeFormat().resolvedOptions().timeZone
      : "UTC";
  if (TIMEZONE_OPTIONS.some((z) => z.value === detected)) {
    return detected;
  }
  return detected || "UTC";
}

/** Options plus browser timezone if it isn’t already listed. */
export function timezoneOptionsForSelect(
  current: string,
): TimezoneOption[] {
  if (TIMEZONE_OPTIONS.some((z) => z.value === current)) {
    return TIMEZONE_OPTIONS;
  }
  return [
    { value: current, label: current.replace(/_/g, " ") },
    ...TIMEZONE_OPTIONS,
  ];
}
