import { expect, test } from "@playwright/test";

test("register, review an alert, save an action, and log out", async ({ page }) => {
  const email = `e2e-${Date.now()}@example.com`;
  const password = "CropShield-demo-123";

  await page.goto("/register");
  await page.getByLabel("Full name", { exact: true }).fill("E2E Demo User");
  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByLabel("Confirm password", { exact: true }).fill(password);
  const registrationResponse = page.waitForResponse((response) =>
    new URL(response.url()).pathname.endsWith("/api/auth/register") &&
    response.request().method() === "POST"
  );
  await page.getByRole("button", { name: "Create account" }).click();
  const registration = await registrationResponse;
  const registrationBody = await registration.json() as { code?: string; detail?: string };
  expect(
    registration.status(),
    `${registrationBody.code ?? "unknown"}: ${registrationBody.detail ?? "No API detail"}`
  ).toBe(201);
  await expect(page).toHaveURL("/");

  await page.getByRole("status").filter({ hasText: "Synthetic" }).waitFor();
  await expect(page.getByRole("region", { name: "Regional summary" })).toBeVisible();
  await expect(page.locator(".leaflet-container")).toBeVisible();
  await expect(page.getByRole("heading", { name: "Top fields to inspect" })).toBeVisible();

  const accountMenu = page.locator("header details").filter({ hasText: email });
  await accountMenu.locator("summary").click();
  await accountMenu.getByRole("button", { name: "Sign out" }).click();
  await expect(page).toHaveURL(/\/login$/);

  await page.getByLabel("Email address", { exact: true }).fill(email);
  await page.getByLabel("Password", { exact: true }).fill(password);
  await page.getByRole("button", { name: "Sign in" }).click();
  await expect(page).toHaveURL("/");

  const alertFieldLink = page
    .locator('aside[aria-labelledby="top-fields-heading"] a[href^="/fields/"]')
    .filter({ hasText: "Alert" })
    .first();
  await expect(alertFieldLink).toBeVisible();
  await alertFieldLink.click();
  await expect(page).toHaveURL(/\/fields\/.+/);
  await expect(page.getByText("Vegetation index over time", { exact: true })).toBeVisible();
  await expect(page.locator(".recharts-surface").first()).toBeVisible();
  await expect(page.getByText(/baseline|uncertainty band/i).first()).toBeVisible();

  await page.getByRole("combobox", { name: "Language" }).selectOption("mr");
  await expect(page.getByRole("combobox", { name: "भाषा" })).toHaveValue("mr");

  await page.getByLabel("स्थिती", { exact: false }).selectOption("done");
  const actionNote = `E2E inspection ${Date.now()}`;
  await page.getByLabel("नोंद", { exact: true }).fill(actionNote);
  await page.getByRole("button", { name: "कृती नोंदवा" }).click();
  await expect(page.getByText(actionNote)).toBeVisible();
  await page.reload();
  await expect(page.getByText(actionNote)).toBeVisible();

  const marathiAccountMenu = page.locator("header details").filter({ hasText: email });
  await marathiAccountMenu.locator("summary").click();
  await marathiAccountMenu.getByRole("button", { name: "साइन आउट" }).click();
  await expect(page).toHaveURL(/\/login$/);
  await page.goto("/");
  await expect(page).toHaveURL(/\/login$/);
});
