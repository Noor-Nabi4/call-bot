/** Pure formatters for Phase 32 usage cost UI (safe for node:test). */

export function formatNullableUsd(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    maximumFractionDigits: 2,
  }).format(value);
}

export function formatNullablePct(value: number | null | undefined): string {
  if (value === null || value === undefined) return "N/A";
  return `${value.toFixed(1)}%`;
}

export function provenanceLabel(p: string | undefined): string {
  switch (p) {
    case "ACTUAL_PROVIDER":
      return "Actual";
    case "ACTUAL_INTERNAL":
      return "Internal";
    case "CONFIGURED_RATE":
      return "Configured";
    case "ALLOCATED_COST":
      return "Allocated";
    case "ESTIMATED":
      return "Estimated";
    case "UNAVAILABLE":
      return "Unavailable";
    default:
      return p || "Unknown";
  }
}
