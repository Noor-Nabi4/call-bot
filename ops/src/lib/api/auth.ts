import { api } from "./client";
import type { OpsUser } from "@/types";

export function login(body: {
  email: string;
  password: string;
  tenant_slug: string;
}) {
  return api<{ user: OpsUser }>("/auth/login", {
    method: "POST",
    body: JSON.stringify(body),
  });
}

export function logout() {
  return api<{ ok: boolean }>("/auth/logout", { method: "POST" });
}

export function me() {
  return api<{ user: OpsUser }>("/auth/me");
}

export function updateProfile(body: {
  name?: string;
  current_password?: string;
  new_password?: string;
}) {
  return api<{ user: OpsUser }>("/auth/me", {
    method: "PUT",
    body: JSON.stringify(body),
  });
}
