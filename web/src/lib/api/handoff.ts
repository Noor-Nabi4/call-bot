import type { HandoffSettings } from "@/types";
import { api } from "./client";

export function getHandoffSettings() {
  return api<{ settings: HandoffSettings }>("/api/handoff");
}
