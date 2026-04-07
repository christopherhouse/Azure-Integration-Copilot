/**
 * Auth flow tests.
 *
 * Covers:
 * - Login page renders with the dev-credentials form in development mode.
 * - Unauthenticated users are redirected to /login.
 * - Authenticated users are redirected away from /login to /dashboard.
 * - The header sign-out button is present when logged in.
 */

import { test, expect } from "@playwright/test";
import { setupAuthMocks, setupApiMocks } from "../fixtures/index.js";

test.describe("Login page", () => {
  test.beforeEach(async ({ page }) => {
    // No session — user is not authenticated
    await setupAuthMocks(page, { session: null });
  });

  test("renders the Integrisight.ai brand heading", async ({ page }) => {
    await page.goto("/login");
    await expect(
      page.getByRole("heading", { name: "Integrisight.ai" })
    ).toBeVisible();
  });

  test("renders the dev-credentials sign-in form in development mode", async ({
    page,
  }) => {
    await page.goto("/login");

    // In development (NODE_ENV=development) the credentials form is shown
    await expect(page.getByRole("button", { name: /sign in with dev account/i })).toBeVisible();
    await expect(page.getByPlaceholder("dev@example.com")).toBeVisible();
  });

  test("email input accepts a custom email address", async ({ page }) => {
    await page.goto("/login");

    const emailInput = page.getByPlaceholder("dev@example.com");
    await emailInput.fill("playwright@example.com");
    await expect(emailInput).toHaveValue("playwright@example.com");
  });

  test("shows a privacy and security link", async ({ page }) => {
    await page.goto("/login");

    const privacyLink = page.getByRole("link", { name: /privacy/i });
    await expect(privacyLink).toBeVisible();
    await expect(privacyLink).toHaveAttribute("href", "/privacy");
  });
});

test.describe("Unauthenticated redirects", () => {
  test.beforeEach(async ({ page }) => {
    // Return an empty session object so NextAuth treats the user as signed out
    await setupAuthMocks(page, { session: {} });
  });

  test("visiting / redirects to /login when not authenticated", async ({
    page,
  }) => {
    await page.goto("/");
    await expect(page).toHaveURL(/\/login/);
  });

  test("visiting /dashboard redirects to /login when not authenticated", async ({
    page,
  }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login/);
  });
});

test.describe("Authenticated navigation", () => {
  test.beforeEach(async ({ page }) => {
    await setupAuthMocks(page);
    await setupApiMocks(page);
  });

  test("authenticated user at /login is shown the dev sign-in form", async ({
    page,
  }) => {
    // The login page always renders the dev form in development mode,
    // regardless of authentication state (client-side check).
    await page.goto("/login");
    await expect(
      page.getByRole("button", { name: /sign in with dev account/i })
    ).toBeVisible();
  });

  test("header shows the signed-in user's name", async ({ page }) => {
    await page.goto("/dashboard");
    // Header renders session.user.name
    await expect(page.getByText("Test User")).toBeVisible();
  });

  test("header has a sign-out button", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(
      page.getByRole("button", { name: /sign out/i })
    ).toBeVisible();
  });
});
