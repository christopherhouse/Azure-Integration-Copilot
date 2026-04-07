/**
 * Project detail page tests.
 *
 * Covers:
 * - Page renders the project name and status badge.
 * - Overview tab shows artifact count, graph version, and status cards.
 * - Overview tab shows project detail metadata (created date, created by).
 * - Artifacts tab shows the upload area and artifact list.
 * - Graph tab shows the canvas or the empty-state placeholder.
 * - Settings tab shows the edit-project section and the danger zone.
 * - Delete-project confirmation dialog opens and can be dismissed.
 * - Analyze button navigates to the analysis page.
 */

import { test, expect } from "../fixtures/index.js";
import { setupApiMocks, setupAuthMocks } from "../fixtures/index.js";
import {
  MOCK_PROJECT_1,
  MOCK_ARTIFACT_1,
  MOCK_ARTIFACT_2,
  MOCK_GRAPH_SUMMARY,
} from "../fixtures/mock-data.js";

const PROJECT_URL = `/dashboard/projects/${MOCK_PROJECT_1.id}`;

test.describe("Project detail — header", () => {
  test("displays the project name", async ({ authenticatedPage: page }) => {
    await page.goto(PROJECT_URL);
    await expect(
      page.getByRole("heading", { name: MOCK_PROJECT_1.name })
    ).toBeVisible();
  });

  test("displays the project status badge", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);
    // Use the specific badge element in the project header (not the Overview tab card)
    await expect(
      page.getByRole("main").locator('[data-slot="badge"]').first()
    ).toContainText(MOCK_PROJECT_1.status);
  });

  test("Analyze button links to the analysis page", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);

    const analyzeLink = page.getByRole("link", { name: /analyze/i });
    await expect(analyzeLink).toBeVisible();
    await expect(analyzeLink).toHaveAttribute(
      "href",
      `/dashboard/projects/${MOCK_PROJECT_1.id}/analysis`
    );
  });
});

test.describe("Project detail — Overview tab", () => {
  test("shows the artifact count card", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);

    // Scope to the Overview tabpanel to avoid strict mode violations
    const overviewPanel = page.getByRole("tabpanel", { name: "Overview" });
    await expect(overviewPanel.getByText("Artifacts").first()).toBeVisible();
    await expect(
      overviewPanel.getByText(String(MOCK_PROJECT_1.artifactCount)).first()
    ).toBeVisible();
  });

  test("shows the graph version card", async ({ authenticatedPage: page }) => {
    await page.goto(PROJECT_URL);

    const overviewPanel = page.getByRole("tabpanel", { name: "Overview" });
    await expect(overviewPanel.getByText("Graph Version")).toBeVisible();
    await expect(
      overviewPanel.getByText(String(MOCK_PROJECT_1.graphVersion)).first()
    ).toBeVisible();
  });

  test("shows the project status in the stats card", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);

    const overviewPanel = page.getByRole("tabpanel", { name: "Overview" });
    await expect(overviewPanel.getByText("Status")).toBeVisible();
  });

  test("shows the created-by name in the details card", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);

    // "Created by" label + value — scope to the Details card term/definition pairs
    const overviewPanel = page.getByRole("tabpanel", { name: "Overview" });
    await expect(overviewPanel.getByText("Created by")).toBeVisible();
    // Use first() because "Test User" may appear for both Created by and Updated by
    await expect(
      overviewPanel.getByText(MOCK_PROJECT_1.createdByName as string).first()
    ).toBeVisible();
  });
});

test.describe("Project detail — Artifacts tab", () => {
  test("clicking Artifacts tab shows the upload area", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);

    await page.getByRole("tab", { name: /artifacts/i }).click();

    // ArtifactUpload renders a label with "Drop files here or click to upload"
    await expect(
      page.getByText("Drop files here or click to upload")
    ).toBeVisible();
  });

  test("artifacts tab lists uploaded artifacts", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);

    await page.getByRole("tab", { name: /artifacts/i }).click();

    await expect(page.getByText(MOCK_ARTIFACT_1.name)).toBeVisible();
    await expect(page.getByText(MOCK_ARTIFACT_2.name)).toBeVisible();
  });
});

test.describe("Project detail — Graph tab", () => {
  test("graph tab shows graph summary when data is available", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);

    await page.getByRole("tab", { name: /graph/i }).click();

    // GraphSummary renders "Components" and "Edges" descriptions
    const graphPanel = page.getByRole("tabpanel", { name: "Graph" });
    await expect(graphPanel.getByText("Components").first()).toBeVisible();
    await expect(graphPanel.getByText("Edges").first()).toBeVisible();
  });

  test("graph tab shows empty-state placeholder when no graph data exists", async ({
    page,
  }) => {
    await setupAuthMocks(page);
    await setupApiMocks(page, { graphSummary: null });

    await page.goto(PROJECT_URL);

    await page.getByRole("tab", { name: /graph/i }).click();

    await expect(
      page.getByText(/graph visualization will appear here/i)
    ).toBeVisible();
  });
});

test.describe("Project detail — Settings tab", () => {
  test("settings tab shows the Edit Project section", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);

    await page.getByRole("tab", { name: /settings/i }).click();

    await expect(page.getByText("Project Details")).toBeVisible();
  });

  test("settings tab shows the Danger Zone", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);

    await page.getByRole("tab", { name: /settings/i }).click();

    await expect(page.getByText("Danger Zone")).toBeVisible();
  });

  test("clicking Delete Project opens a confirmation dialog", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);

    await page.getByRole("tab", { name: /settings/i }).click();

    await page.getByRole("button", { name: /delete project/i }).click();

    await expect(page.getByRole("dialog")).toBeVisible();
    await expect(
      page.getByText(/are you sure you want to delete/i)
    ).toBeVisible();
  });

  test("delete confirmation dialog can be dismissed with Cancel", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(PROJECT_URL);

    await page.getByRole("tab", { name: /settings/i }).click();

    await page.getByRole("button", { name: /delete project/i }).click();
    await expect(page.getByRole("dialog")).toBeVisible();

    await page.getByRole("button", { name: /cancel/i }).click();
    await expect(page.getByRole("dialog")).not.toBeVisible();
  });
});
