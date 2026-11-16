import { readFileSync } from "node:fs";
import path from "node:path";

export type E2ETenant = {
  slug: string;
  name: string;
  email: string;
  password: string;
  tenant_id: string;
  mode: "no_phone" | "with_phone" | "pending_phone";
  phone_e164: string | null;
};

export type E2EFixtures = {
  api_url: string;
  web_url: string;
  tenants: {
    no_phone: E2ETenant;
    with_phone: E2ETenant;
    pending_phone: E2ETenant;
  };
};

const fixturesPath = path.join(__dirname, "..", ".auth", "fixtures.json");

export function loadFixtures(): E2EFixtures {
  return JSON.parse(readFileSync(fixturesPath, "utf8")) as E2EFixtures;
}
