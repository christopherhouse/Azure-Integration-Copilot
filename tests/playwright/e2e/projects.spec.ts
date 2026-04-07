/**
 * Projects list page tests.
 *
 * Covers:
 * - Projects page renders the page heading.
 * - Listed projects show name and artifact count.
 * - Empty state is shown when there are no projects.
 * - Create-project dialog opens and shows required fields.
 * - Clicking a project card navigates to the project detail page.
 */

import { test, expect, setupApiMocks, setupAuthMocks } from "../fixtures/index.js";
import {
  MOCK_EMPTY_PROJECTS_RESPONSE,
  MOCK_PROJECT_1,
  MOCK_PROJECT_2,
} from "../fixtures/mock-data.js";

test.describe("Projects list page", () => {
  test("renders the Projects heading", async ({ authenticatedPage: page }) => {
    await page.goto("/dashboard");
    await expect(
      page.getByRole("heading", { name: "Projects" })
    ).toBeVisible();
  });

  test("shows the Create Project button", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/dashboard");
    await expect(
      page.getByRole("button", { name: /new project/i })
    ).toBeVisible();
  });

  test("lists all projects returned by the API", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/dashboard");

    await expect(page.getByText(MOCK_PROJECT_1.name)).toBeVisible();
    await expect(page.getByText(MOCK_PROJECT_2.name)).toBeVisible();
  });

  test("shows project descriptions", async ({ authenticatedPage: page }) => {
    await page.goto("/dashboard");

    await expect(
      page.getByText(MOCK_PROJECT_1.description as string)
    ).toBeVisible();
  });

  test("shows artifact count for each project", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/dashboard");

    // "3 artifacts" for project 1
    await expect(
      page.getByText(`${MOCK_PROJECT_1.artifactCount} artifact`)
    ).toBeVisible();
  });

  test("shows empty state when no projects exist", async ({ page }) => {
    // Apply auth mocks before API mocks — same order as authenticatedPage fixture
    await setupAuthMocks(page);
    // Override projects response with empty list
    await setupApiMocks(page, { projects: MOCK_EMPTY_PROJECTS_RESPONSE });

    await page.goto("/dashboard");

    await expect(
      page.getByText(/no projects yet/i)
    ).toBeVisible();
  });

  test("clicking a project card navigates to the project detail page", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/dashboard");

    await page.getByText(MOCK_PROJECT_1.name).click();

    await expect(page).toHaveURL(
      new RegExp(`/dashboard/projects/${MOCK_PROJECT_1.id}`)
    );
  });
});

test.describe("Create Project dialog", () => {
  test("opens when the New Project button is clicked", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/dashboard");

    await page.getByRole("button", { name: /new project/i }).click();

    // Dialog should now be visible — look for the Name input or dialog heading
    await expect(
      page.getByRole("dialog")
    ).toBeVisible();
  });

  test("dialog contains a Name field", async ({
    authenticatedPage: page,
  }) => {
    await page.goto("/dashboard");

    await page.getByRole("button", { name: /new project/i }).click();

    await expect(
      page.getByLabel(/name/i)
    ).toBeVisible();
  });

  test("dialog can be dismissed", async ({ authenticatedPage: page }) => {
    await page.goto("/dashboard");

    await page.getByRole("button", { name: /new project/i }).click();
    await expect(page.getByRole("dialog")).toBeVisible();

    // Press Escape to close
    await page.keyboard.press("Escape");
    await expect(page.getByRole("dialog")).not.toBeVisible();
  });
});
