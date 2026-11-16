/** Pure helpers for agent config UI (safe for node:test). */

export function riskLabel(level: string): string {
  if (level === "high") return "High risk";
  if (level === "medium") return "Medium risk";
  return "Low risk";
}

export function categoryLabel(category: string): string {
  const map: Record<string, string> = {
    customer_calls: "Customer & Calls",
    scheduling: "Scheduling",
    crm: "CRM",
    commerce: "Commerce",
    payments: "Payments",
    messaging: "Messaging",
  };
  return map[category] || category;
}
