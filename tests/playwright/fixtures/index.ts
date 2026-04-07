/**
 * Extended Playwright test fixture.
 *
 * Provides:
 * - `authenticatedPage` — a Page with NextAuth session and all backend API
 *   routes intercepted with realistic mock responses.
 * - `setupApiMocks(page, overrides?)` — helper to register mock API routes
 *   on any Page object, with optional per-test response overrides.
 */

import { test as base, type Page, type Route } from "@playwright/test";
import {
  MOCK_SESSION,
  MOCK_TENANT,
  MOCK_USER,
  MOCK_PROJECTS_RESPONSE,
  MOCK_PROJECT_1,
  MOCK_ARTIFACTS_RESPONSE,
  MOCK_ANALYSES_RESPONSE,
  MOCK_GRAPH_SUMMARY,
  MOCK_GRAPH_COMPONENTS_RESPONSE,
  MOCK_GRAPH_EDGES_RESPONSE,
  MOCK_REALTIME_NEGOTIATE,
} from "./mock-data.js";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

/** Partial overrides for mock responses used in individual tests. */
export interface MockOverrides {
  session?: Record<string, unknown> | null;
  tenant?: Record<string, unknown> | null;
  projects?: Record<string, unknown>;
  project?: Record<string, unknown>;
  artifacts?: Record<string, unknown>;
  analyses?: Record<string, unknown>;
  graphSummary?: Record<string, unknown> | null;
  graphComponents?: Record<string, unknown>;
  graphEdges?: Record<string, unknown>;
}

// ---------------------------------------------------------------------------
// Helper: fulfill with JSON
// ---------------------------------------------------------------------------

function json(route: Route, body: unknown, status = 200): Promise<void> {
  return route.fulfill({
    status,
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

// ---------------------------------------------------------------------------
// Setup: mock NextAuth session
// ---------------------------------------------------------------------------

export async function setupAuthMocks(
  page: Page,
  overrides?: Pick<MockOverrides, "session">
): Promise<void> {
  const session =
    overrides?.session !== undefined ? overrides.session : MOCK_SESSION;

  // NextAuth session endpoint — determines whether the user is logged in
  await page.route("**/api/auth/session", (route) =>
    json(route, session ?? {})
  );

  // NextAuth CSRF token endpoint — required for sign-in form submissions
  await page.route("**/api/auth/csrf", (route) =>
    json(route, { csrfToken: "mock-csrf-token-playwright" })
  );

  // NextAuth providers list — used by some sign-in pages
  await page.route("**/api/auth/providers", (route) =>
    json(route, {
      "dev-credentials": {
        id: "dev-credentials",
        name: "Dev Credentials",
        type: "credentials",
        signinUrl: "http://localhost:3000/api/auth/signin/dev-credentials",
        callbackUrl: "http://localhost:3000/api/auth/callback/dev-credentials",
      },
    })
  );
}

// ---------------------------------------------------------------------------
// Setup: mock backend API endpoints
// ---------------------------------------------------------------------------

export async function setupApiMocks(
  page: Page,
  overrides: MockOverrides = {}
): Promise<void> {
  const projectData =
    overrides.project !== undefined ? overrides.project : MOCK_PROJECT_1;
  const projectsData =
    overrides.projects !== undefined ? overrides.projects : MOCK_PROJECTS_RESPONSE;
  const artifactsData =
    overrides.artifacts !== undefined
      ? overrides.artifacts
      : MOCK_ARTIFACTS_RESPONSE;
  const analysesData =
    overrides.analyses !== undefined
      ? overrides.analyses
      : MOCK_ANALYSES_RESPONSE;

  // All backend API calls go through the API base URL. By default this is
  // http://localhost:8000 (set via API_BASE_URL env in the webServer config).
  await page.route("**/api/v1/**", (route) => {
    const url = route.request().url();

    // --- Tenant ---
    if (url.includes("/api/v1/tenants/me")) {
      const tenantBody =
        overrides.tenant !== undefined ? overrides.tenant : MOCK_TENANT;
      return json(route, {
        meta: { requestId: "req-tenant", timestamp: new Date().toISOString() },
        data: tenantBody,
      });
    }

    // --- User profile ---
    if (url.includes("/api/v1/users/me")) {
      return json(route, {
        meta: { requestId: "req-user", timestamp: new Date().toISOString() },
        data: MOCK_USER,
      });
    }

    // --- Graph summary ---
    if (url.includes("/graph/summary")) {
      const summary =
        overrides.graphSummary !== undefined
          ? overrides.graphSummary
          : MOCK_GRAPH_SUMMARY;
      return json(route, {
        meta: { requestId: "req-graph-summary", timestamp: new Date().toISOString() },
        data: summary,
      });
    }

    // --- Graph components ---
    if (url.includes("/graph/components")) {
      const components =
        overrides.graphComponents !== undefined
          ? overrides.graphComponents
          : MOCK_GRAPH_COMPONENTS_RESPONSE;
      return json(route, components);
    }

    // --- Graph edges ---
    if (url.includes("/graph/edges")) {
      const edges =
        overrides.graphEdges !== undefined
          ? overrides.graphEdges
          : MOCK_GRAPH_EDGES_RESPONSE;
      return json(route, edges);
    }

    // --- Analyses ---
    if (url.includes("/analyses")) {
      return json(route, analysesData);
    }

    // --- Artifacts ---
    if (url.includes("/artifacts")) {
      return json(route, artifactsData);
    }

    // --- Single project (GET /api/v1/projects/:id) ---
    if (/\/api\/v1\/projects\/[^/]+$/.test(new URL(url).pathname)) {
      return json(route, {
        meta: { requestId: "req-project", timestamp: new Date().toISOString() },
        data: projectData,
      });
    }

    // --- Projects list ---
    if (url.includes("/api/v1/projects")) {
      return json(route, projectsData);
    }

    // --- Realtime negotiate ---
    if (url.includes("/api/v1/realtime/negotiate")) {
      return json(route, {
        meta: { requestId: "req-rt", timestamp: new Date().toISOString() },
        data: MOCK_REALTIME_NEGOTIATE,
      });
    }

    // Fallback — let unmapped requests through (avoids silent failures)
    return route.continue();
  });
}

// ---------------------------------------------------------------------------
// Extended fixtures
// ---------------------------------------------------------------------------

type TestFixtures = {
  /** A page that has both auth and API mocks pre-applied. */
  authenticatedPage: Page;
};

export const test = base.extend<TestFixtures>({
  authenticatedPage: async ({ page }, use) => {
    await setupAuthMocks(page);
    await setupApiMocks(page);
    await use(page);
  },
});

export { expect } from "@playwright/test";
