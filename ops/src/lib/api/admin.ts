import type { Appointment, Call, CustomerOption } from "@/types";
import { api } from "./client";

export function listAppointments() {
  return api<{ appointments: Appointment[] }>("/api/admin/appointments");
}

export function listCalls() {
  return api<{ calls: Call[] }>("/api/admin/calls");
}

export function listCustomers() {
  return api<{ customers: CustomerOption[] }>("/api/admin/customers").then(
    (d) => ({
      customers: (d.customers || []).map((c) => ({
        id: c.id,
        name: c.name,
      })),
    }),
  );
}
