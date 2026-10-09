import { execFileSync } from "node:child_process";
import path from "node:path";

/**
 * Seeds Postgres tenants for phone-gate browser tests via platform helpers.
 * Requires platform API + web already running (does not start servers).
 */
export default function globalSetup(): void {
  const script = path.join(__dirname, "scripts", "seed_phone_gate.py");
  const platformDir = path.resolve(__dirname, "../../platform");

  execFileSync("uv", ["run", "python", script], {
    cwd: platformDir,
    stdio: "inherit",
    env: {
      ...process.env,
      PLAYWRIGHT_BASE_URL:
        process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:3002",
      PLATFORM_API_URL:
        process.env.PLATFORM_API_URL ??
        process.env.NEXT_PUBLIC_PLATFORM_API_URL ??
        "http://127.0.0.1:8000",
    },
  });
}
