import type { Appointment, Call, CustomerOption } from "@/types";
import { api } from "./client";

export type TeamUser = {
  id: string;
  email: string;
  name: string;
  role: string;
  is_active: boolean;
};

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

export function listTeamUsers() {
  return api<{ users: TeamUser[] }>("/api/admin/users");
}

export function inviteTeamUser(body: {
  name: string;
  email: string;
  password: string;
  role: string;
  phone?: string;
}) {
  return api<{ user: TeamUser }>("/api/admin/users", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function updateTeamUser(
  userId: string,
  body: {
    name?: string;
    role?: string;
    is_active?: boolean;
    password?: string;
  },
) {
  return api<{ user: TeamUser }>(`/api/admin/users/${userId}`, {
    method: "PATCH",
    body: JSON.stringify(body),
  });
}
