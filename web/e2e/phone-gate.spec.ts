import { execFileSync } from "node:child_process";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { loginAs } from "./helpers/auth";
import { loadFixtures } from "./helpers/fixtures";

const platformDir = path.resolve(__dirname, "../../platform");
const mutateScript = path.resolve(__dirname, "scripts/mutate_phone.py");

function mutatePhone(tenantId: string, action: "lose" | "restore"): void {
  execFileSync(
    "uv",
    ["run", "python", mutateScript, "--tenant-id", tenantId, "--action", action],
    { cwd: platformDir, stdio: "inherit", env: process.env },
  );
}

test.describe("mandatory phone access gate (browser)", () => {
  test("completed org without phone is sent to phone setup, not dashboard", async ({
    page,
  }) => {
    const { tenants } = loadFixtures();
    const tenant = tenants.no_phone;

    await loginAs(page, tenant);
    await expect(page).toHaveURL(/\/phones(\?|$)/);
    await expect(page.getByRole("heading", { name: "Phones" })).toBeVisible();
    await expect(
      page.getByText("Connect a number you already own", { exact: true }),
    ).toBeVisible();
    await expect(
      page.getByText("purchase a new number", { exact: true }),
    ).toBeVisible();

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/(phones|onboarding)/);
  });

  test("pending provisioning stays blocked and phones UI remains available", async ({
    page,
  }) => {
    const { tenants } = loadFixtures();
    const tenant = tenants.pending_phone;

    await loginAs(page, tenant);
    await expect(page).toHaveURL(/\/phones/);
    await expect(page.getByRole("heading", { name: "Phones" })).toBeVisible();

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/(phones|onboarding)/);
  });

  test("eligible number reaches dashboard without opening buy flow", async ({
    page,
  }) => {
    const { tenants } = loadFixtures();
    const tenant = tenants.with_phone;

    await loginAs(page, tenant);
    await expect(page).toHaveURL(/\/dashboard/);
    await expect(
      page.getByText(/needs your attention|Active jobs|Calls today/i).first(),
    ).toBeVisible();

    // Should not land on purchase/connect as a gate redirect.
    await expect(page).not.toHaveURL(/\/phones/);
  });

  test("BYON and purchase drawers open; purchase requires confirmation", async ({
    page,
  }) => {
    const { tenants } = loadFixtures();
    const tenant = tenants.no_phone;
    let purchasePosts = 0;

    // Stub Twilio-backed endpoints so confirmation UX can be asserted without
    // live provider credentials. Real purchase remains staging-only.
    await page.route("**/api/admin/twilio/subaccount", async (route) => {
      if (route.request().method() === "POST") {
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true }),
        });
        return;
      }
      await route.continue();
    });
    await page.route("**/api/admin/inventory**", async (route) => {
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        body: JSON.stringify({
          items: [
            {
              e164: "+14155550100",
              locality: "San Francisco",
              monthly_price: "$1.15",
            },
          ],
        }),
      });
    });
    await page.route("**/api/admin/phone-numbers/purchase", async (route) => {
      if (route.request().method() === "POST") {
        purchasePosts += 1;
        await route.fulfill({
          status: 200,
          contentType: "application/json",
          body: JSON.stringify({ ok: true, e164: "+14155550100" }),
        });
        return;
      }
      await route.continue();
    });

    await loginAs(page, tenant);
    await expect(page).toHaveURL(/\/phones/);

    await page.getByRole("button", { name: "Connect", exact: true }).first().click();
    const connectDialog = page.getByRole("dialog", {
      name: "Connect existing number",
    });
    await expect(connectDialog).toBeVisible();
    await expect(page.getByPlaceholder("+15551234567")).toBeVisible();
    await connectDialog.getByRole("button", { name: "Cancel" }).click();

    await page.getByRole("button", { name: "Buy number" }).first().click();
    const buyDialog = page.getByRole("dialog", { name: "Buy number" });
    await expect(buyDialog).toBeVisible();
    await expect(page.getByPlaceholder("415")).toBeVisible();
    await page.getByPlaceholder("415").fill("415");
    await buyDialog.getByRole("button", { name: "Search" }).click();
    await expect(page.getByText("+14155550100")).toBeVisible();
    await expect(page.getByText("$1.15")).toBeVisible();

    await buyDialog.getByRole("button", { name: "Buy", exact: true }).click();
    const confirm = page.getByRole("alertdialog", { name: "Buy this number?" });
    await expect(confirm).toBeVisible();
    await confirm.getByRole("button", { name: "Cancel" }).click();
    expect(purchasePosts).toBe(0);

    await buyDialog.getByRole("button", { name: "Buy", exact: true }).click();
    await expect(confirm).toBeVisible();
    await confirm.getByRole("button", { name: "Buy number" }).click();
    await expect.poll(() => purchasePosts).toBe(1);
  });

  test("losing the last eligible number re-blocks dashboard; restore unlocks", async ({
    page,
  }) => {
    const { tenants } = loadFixtures();
    const tenant = tenants.with_phone;

    await loginAs(page, tenant);
    await expect(page).toHaveURL(/\/dashboard/);

    mutatePhone(tenant.tenant_id, "lose");

    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/(phones|onboarding)/);

    mutatePhone(tenant.tenant_id, "restore");

    await page.goto("/login");
    await loginAs(page, tenant);
    await expect(page).toHaveURL(/\/dashboard/);
  });
});
