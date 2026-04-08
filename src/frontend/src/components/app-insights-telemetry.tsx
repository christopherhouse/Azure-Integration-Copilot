"use client";

import { useAppInsights } from "@/lib/appinsights";

/**
 * Client component that initializes Application Insights browser telemetry.
 *
 * When the runtime config provides an `applicationInsightsConnectionString`,
 * the Application Insights SDK is loaded and begins:
 * - Injecting W3C `traceparent` headers into all outbound fetch/XHR requests
 * - Tracking page views, route changes, and user interactions
 * - Capturing unhandled exceptions and promise rejections
 *
 * This enables true end-to-end distributed tracing from the browser through
 * the backend API and into asynchronous worker pipelines.
 *
 * Render this component inside `<body>` in the root layout — it renders no
 * visible DOM.
 */
export function AppInsightsTelemetry() {
  useAppInsights();
  return null;
}
