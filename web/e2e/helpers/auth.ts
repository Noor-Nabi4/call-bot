import { expect, type Page } from "@playwright/test";
import type { E2ETenant } from "./fixtures";

/** Fill login using placeholders / roles (no CSS class or id selectors). */
export async function loginAs(page: Page, tenant: E2ETenant): Promise<void> {
  await page.goto("/login");
  await expect(page.getByRole("heading", { name: "Sign in" })).toBeVisible();
  await page.getByPlaceholder("your-business").fill(tenant.slug);
  await page.locator('input[type="email"]').fill(tenant.email);
  await page.locator('input[type="password"]').fill(tenant.password);
  await page.getByRole("button", { name: "Sign in" }).click();
}
