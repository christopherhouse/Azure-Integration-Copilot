import { defineConfig, devices } from "@playwright/test";
import path from "path";

/**
 * Playwright configuration for the Integrisight.ai frontend.
 *
 * - Starts the Next.js dev server automatically.
 * - All backend API calls and NextAuth session endpoints are intercepted via
 *   per-test `page.route()` handlers (see tests/playwright/fixtures/index.ts).
 * - Tests run in Chromium by default; add more projects as needed.
 */
export default defineConfig({
  testDir: path.join(__dirname, "../../tests/playwright/e2e"),

  /* Run tests sequentially in CI to avoid port conflicts. */
  fullyParallel: !process.env.CI,

  /* Fail the build on CI if test.only is accidentally left in source. */
  forbidOnly: !!process.env.CI,

  retries: process.env.CI ? 1 : 0,

  workers: process.env.CI ? 1 : undefined,

  reporter: process.env.CI
    ? [["list"], ["junit", { outputFile: "playwright-results.xml" }]]
    : "list",

  use: {
    baseURL: "http://localhost:3000",
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    /* Give each navigation a generous timeout — Next.js dev server can be slow
       on first page compile. */
    navigationTimeout: 30_000,
    actionTimeout: 10_000,
  },

  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"] },
    },
  ],

  /* Automatically start the Next.js dev server before running tests. */
  webServer: {
    command: "npm run dev",
    url: "http://localhost:3000",
    reuseExistingServer: !process.env.CI,
    cwd: __dirname,
    timeout: 120_000,
    env: {
      NODE_ENV: "development",
      NEXTAUTH_URL: "http://localhost:3000",
      /* Use a fixed secret so JWT tokens are deterministic across restarts. */
      NEXTAUTH_SECRET: "playwright-test-secret-do-not-use-in-production",
      /* The API base URL that RuntimeConfig injects into window.__RUNTIME_CONFIG__.
         Tests intercept requests to this origin via page.route(). */
      API_BASE_URL: "http://localhost:8000",
    },
  },
});
