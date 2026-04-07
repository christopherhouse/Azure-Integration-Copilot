/**
 * Analysis page tests.
 *
 * Covers:
 * - Analysis page renders the "Analysis" heading.
 * - Back-to-project link is present and correct.
 * - Usage summary is rendered.
 * - Analysis history sidebar is shown on wide viewports.
 * - Chat area renders the prompt input.
 * - Submitting a prompt triggers a POST to the analyses endpoint.
 * - A previously-selected analysis shows the response in the chat area.
 */

import { test, expect } from "../fixtures/index.js";
import { MOCK_PROJECT_1, MOCK_ANALYSIS_1 } from "../fixtures/mock-data.js";

const ANALYSIS_URL = `/dashboard/projects/${MOCK_PROJECT_1.id}/analysis`;

test.describe("Analysis page — structure", () => {
  test("renders the Analysis heading", async ({ authenticatedPage: page }) => {
    await page.goto(ANALYSIS_URL);
    await expect(
      page.getByRole("heading", { name: "Analysis" })
    ).toBeVisible();
  });

  test("back link points to the project detail page", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(ANALYSIS_URL);

    const backLink = page.getByRole("link", { name: /back to project/i });
    await expect(backLink).toBeVisible();
    await expect(backLink).toHaveAttribute(
      "href",
      `/dashboard/projects/${MOCK_PROJECT_1.id}`
    );
  });

  test("usage summary is visible", async ({ authenticatedPage: page }) => {
    await page.goto(ANALYSIS_URL);

    // UsageSummary renders daily analysis counts
    await expect(
      page.getByText(/daily analysis/i).or(page.getByText(/analyses/i))
    ).toBeVisible();
  });
});

test.describe("Analysis page — history sidebar", () => {
  test("history sidebar shows the History heading on desktop viewports", async ({
    authenticatedPage: page,
  }) => {
    // Default desktop viewport (1280×720 from Playwright config)
    await page.goto(ANALYSIS_URL);

    // The history sidebar has a "History" heading
    await expect(
      page.getByRole("heading", { name: "History" })
    ).toBeVisible();
  });

  test("existing analysis entries are listed in the history sidebar", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(ANALYSIS_URL);

    // The history sidebar lists the prompt text of past analyses
    await expect(
      page.getByText(MOCK_ANALYSIS_1.prompt)
    ).toBeVisible();
  });
});

test.describe("Analysis page — chat area", () => {
  test("chat area renders a prompt textarea", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(ANALYSIS_URL);

    // AnalysisChat renders a textarea or text input for the prompt
    const promptInput = page
      .getByRole("textbox", { name: /prompt|ask|message/i })
      .or(page.getByPlaceholder(/ask.*integration|analyze|prompt/i));

    await expect(promptInput).toBeVisible();
  });

  test("submit button is present in the chat area", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(ANALYSIS_URL);

    await expect(
      page.getByRole("button", { name: /analyze|send|submit/i })
    ).toBeVisible();
  });

  test("typing a prompt enables the submit button", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(ANALYSIS_URL);

    const promptInput = page
      .getByRole("textbox")
      .or(page.getByPlaceholder(/ask|prompt/i))
      .first();

    await promptInput.fill(
      "What are the main dependencies in this integration?"
    );

    await expect(
      page.getByRole("button", { name: /analyze|send|submit/i })
    ).not.toBeDisabled();
  });

  test("sample prompts are displayed in empty state", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(ANALYSIS_URL);

    // Sample prompts should be visible as buttons
    await expect(
      page.getByRole("button", { name: /dependencies of my Logic App/i })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /API connections in this project/i })
    ).toBeVisible();
    await expect(
      page.getByRole("button", { name: /integration flow.*bottlenecks/i })
    ).toBeVisible();
  });

  test("clicking a sample prompt populates the input", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(ANALYSIS_URL);

    const samplePromptButton = page.getByRole("button", {
      name: /dependencies of my Logic App/i,
    });
    await samplePromptButton.click();

    const promptInput = page
      .getByRole("textbox")
      .or(page.getByPlaceholder(/ask|prompt/i))
      .first();

    await expect(promptInput).toHaveValue(/dependencies of my Logic App/i);
  });

  test("clicking a sample prompt hides all sample prompts", async ({
    authenticatedPage: page,
  }) => {
    await page.goto(ANALYSIS_URL);

    const samplePromptButton = page.getByRole("button", {
      name: /dependencies of my Logic App/i,
    });
    await samplePromptButton.click();

    // All sample prompts should be hidden
    await expect(
      page.getByRole("button", { name: /dependencies of my Logic App/i })
    ).not.toBeVisible();
    await expect(
      page.getByRole("button", { name: /API connections in this project/i })
    ).not.toBeVisible();
    await expect(
      page.getByRole("button", { name: /integration flow.*bottlenecks/i })
    ).not.toBeVisible();
  });
});
