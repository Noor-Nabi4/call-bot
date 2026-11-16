/** Pure helpers for AI business setup UI (safe for node:test without API client). */

export function confidenceLabel(band: string): string {
  if (band === "high") return "High confidence";
  if (band === "medium") return "Medium confidence";
  if (band === "low") return "Low confidence";
  return "Confidence unknown";
}
