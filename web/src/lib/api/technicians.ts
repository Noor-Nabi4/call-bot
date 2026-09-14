import { notifyAttentionChanged } from "@/lib/attention-bus";
import type { Technician } from "@/types";
import { api } from "./client";

export function listTechnicians() {
  return api<{ technicians: Technician[] }>("/api/technicians");
}

export function createTechnician(body: {
  email: string;
  password: string;
  name: string;
  phone?: string;
}) {
  return api<{ technician: Technician }>("/api/technicians", {
    method: "POST",
    body: JSON.stringify(body),
  }).then((res) => {
    notifyAttentionChanged();
    return res;
  });
}

export function pingLocation(lat: number, lng: number) {
  return api<{ technician: Technician }>("/api/tech/location", {
    method: "POST",
    body: JSON.stringify({ lat, lng }),
  });
}
