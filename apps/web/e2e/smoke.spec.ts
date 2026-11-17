import { expect, test } from "@playwright/test";

test("home page shows the core promise and Banking Channels", async ({ page }) => {
  await page.goto("/");
  await expect(page.getByRole("heading", { level: 1 })).toContainText("Experts approve.");
  await expect(page.getByText("Banking Channels")).toBeVisible();
  await expect(page.getByText("Secure card payments processed by Stripe.")).toBeVisible();
  await expect(page.getByText(/PayPal/)).toHaveCount(0);
});

test("status page reports all systems operational", async ({ page }) => {
  await page.goto("/status");
  await expect(page.getByText("All systems operational")).toBeVisible();
  await expect(page.getByText("Database (PostgreSQL)")).toBeVisible();
});

test("planned interfaces are clearly labelled", async ({ page }) => {
  await page.goto("/review");
  await expect(page.getByText(/Not available yet/)).toBeVisible();
});
