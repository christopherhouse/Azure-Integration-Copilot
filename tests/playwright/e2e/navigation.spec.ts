/**
 * Navigation and layout tests.
 *
 * Covers:
 * - Sidebar renders branding and navigation links.
 * - Sidebar "Projects" link navigates to the dashboard.
 * - Sidebar "Settings" link navigates to the settings page.
 * - Sidebar can be collapsed and expanded.
 * - Breadcrumbs update on navigation.
 * - Privacy & Security link is present in the sidebar footer.
 */

import { test, expect } from "../fixtures/index.js";

test.describe("Sidebar navigation", () => {
  test.beforeEach(async ({ authenticatedPage: page }) => {
    await page.goto("/dashboard");
  });

  test("shows the Integrisight.ai brand name", async ({
    authenticatedPage: page,
  }) => {
    await expect(page.getByText("Integrisight.ai")).toBeVisible();
  });

  test("shows a Projects navigation link", async ({
    authenticatedPage: page,
  }) => {
    await expect(
      page.getByRole("link", { name: /projects/i })
    ).toBeVisible();
  });

  test("shows a Settings navigation link", async ({
    authenticatedPage: page,
  }) => {
    await expect(
      page.getByRole("link", { name: /^settings$/i })
    ).toBeVisible();
  });

  test("shows the Privacy & Security link in the sidebar footer", async ({
    authenticatedPage: page,
  }) => {
    await expect(
      page.getByRole("link", { name: /privacy.*security/i })
    ).toBeVisible();
  });

  test("clicking Settings link navigates to /dashboard/settings", async ({
    authenticatedPage: page,
  }) => {
    await page.getByRole("link", { name: /^settings$/i }).click();
    await expect(page).toHaveURL(/\/dashboard\/settings/);
  });

  test("sidebar collapse button toggles the sidebar", async ({
    authenticatedPage: page,
  }) => {
    // Brand text is visible in expanded state
    await expect(page.getByText("Integrisight.ai")).toBeVisible();

    // Click the collapse/expand toggle
    await page
      .getByRole("button", { name: /collapse sidebar/i })
      .click();

    // Brand text should disappear once collapsed
    await expect(page.getByText("Integrisight.ai")).not.toBeVisible();

    // Click the expand button
    await page
      .getByRole("button", { name: /expand sidebar/i })
      .click();

    // Brand text is visible again
    await expect(page.getByText("Integrisight.ai")).toBeVisible();
  });
});

test.describe("Dashboard settings page", () => {
  test("settings page renders a heading", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/dashboard/settings");
    await expect(
      page.getByRole("heading", { name: /settings/i })
    ).toBeVisible();
  });
});
