/**
 * Application Insights browser telemetry client.
 *
 * Provides full distributed tracing from browser to backend by automatically
 * injecting W3C Trace Context headers into all fetch requests. This creates
 * true end-to-end traces that span from user interactions in the browser
 * through backend API calls and worker processing.
 *
 * **When to use:**
 * - Production deployments where full observability is required
 * - Debugging performance issues or complex user flows
 * - Correlating frontend exceptions with backend errors
 *
 * **Trade-offs:**
 * - Adds ~50KB to client bundle (gzipped)
 * - Sends telemetry data to Application Insights from client browsers
 * - Privacy considerations: user IP addresses and session data are collected
 *
 * @see https://learn.microsoft.com/azure/azure-monitor/app/javascript
 * @see https://github.com/microsoft/ApplicationInsights-JS
 */

"use client";

import { ApplicationInsights } from "@microsoft/applicationinsights-web";
import { ReactPlugin } from "@microsoft/applicationinsights-react-js";
import { createBrowserHistory } from "history";
import { useEffect } from "react";

let appInsights: ApplicationInsights | null = null;
let reactPlugin: ReactPlugin | null = null;

/**
 * Initialize Application Insights browser SDK.
 *
 * Should be called once during application bootstrap. The SDK automatically
 * tracks page views, user interactions, exceptions, and AJAX/fetch calls.
 * It injects W3C Trace Context headers into all outbound requests, enabling
 * correlation with backend traces.
 */
export function initializeAppInsights(connectionString: string): void {
  if (appInsights) {
    // Already initialized
    return;
  }

  if (!connectionString) {
    console.warn(
      "[AppInsights] No connection string provided. Browser telemetry disabled."
    );
    return;
  }

  // Create React plugin for route change tracking
  const browserHistory = createBrowserHistory();
  reactPlugin = new ReactPlugin();

  appInsights = new ApplicationInsights({
    config: {
      connectionString,
      enableAutoRouteTracking: true,
      enableRequestHeaderTracking: true,
      enableResponseHeaderTracking: true,
      enableCorsCorrelation: true,
      correlationHeaderExcludedDomains: ["*.google-analytics.com", "*.clarity.ms"],
      disableFetchTracking: false,
      disableAjaxTracking: false,
      autoTrackPageVisitTime: true,
      enableUnhandledPromiseRejectionTracking: true,
      extensions: [reactPlugin],
      extensionConfig: {
        [reactPlugin.identifier]: { history: browserHistory },
      },
    },
  });

  appInsights.loadAppInsights();

  // Track initial page view
  appInsights.trackPageView();

  console.log("[AppInsights] Browser SDK initialized");
}

/**
 * Get the initialized Application Insights instance.
 *
 * Returns null if not initialized. Use this to manually track custom events,
 * metrics, or exceptions beyond automatic instrumentation.
 */
export function getAppInsights(): ApplicationInsights | null {
  return appInsights;
}

/**
 * Get the React plugin instance for use in React components.
 */
export function getReactPlugin(): ReactPlugin | null {
  return reactPlugin;
}

/**
 * React hook to initialize Application Insights on mount.
 *
 * Use this in your root layout or app component to ensure the SDK is
 * initialized before any user interactions occur.
 *
 * @example
 * ```tsx
 * export default function RootLayout({ children }: { children: React.ReactNode }) {
 *   useAppInsights();
 *   return <html>{children}</html>;
 * }
 * ```
 */
export function useAppInsights(): void {
  useEffect(() => {
    // Get connection string from runtime config
    const connectionString =
      typeof window !== "undefined"
        ? window.__RUNTIME_CONFIG__?.applicationInsightsConnectionString
        : undefined;

    if (connectionString) {
      initializeAppInsights(connectionString);
    }
  }, []);
}
