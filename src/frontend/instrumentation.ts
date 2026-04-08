/**
 * Next.js instrumentation hook for server-side OpenTelemetry.
 *
 * This file is automatically loaded by Next.js. It runs once when the Next.js
 * server starts (before any request handling begins), making it the correct
 * place to initialize OpenTelemetry instrumentation for server-side
 * rendering, API routes, and middleware.
 *
 * **Scope:**
 * - Server-side Next.js operations (SSR, getServerSideProps, API routes, middleware)
 * - Outbound HTTP calls made from the Next.js server
 *
 * **Not Included:**
 * - Browser-side telemetry (per Microsoft's recommendation to avoid
 *   client-side OTel instrumentation due to bundle size and privacy concerns)
 *
 * @see https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 * @see https://learn.microsoft.com/azure/azure-monitor/app/opentelemetry-enable?tabs=nodejs
 */

export async function register() {
  // Only run on the server (not in edge runtime or browser)
  if (process.env.NEXT_RUNTIME === "nodejs") {
    const connectionString = process.env.APPLICATIONINSIGHTS_CONNECTION_STRING;

    if (!connectionString) {
      console.warn(
        "[OpenTelemetry] APPLICATIONINSIGHTS_CONNECTION_STRING not set. " +
          "Server-side telemetry disabled."
      );
      return;
    }

    // Dynamically import the Azure Monitor distro and OpenTelemetry APIs to avoid
    // bundling them in edge runtime or browser builds.
    // Note: aliased to avoid ESLint react-hooks/rules-of-hooks false positive
    // (useAzureMonitor is an Azure SDK init function, not a React hook)
    const { useAzureMonitor: initAzureMonitor } = await import("@azure/monitor-opentelemetry");
    const { resourceFromAttributes } = await import("@opentelemetry/resources");

    // Configure Azure Monitor with OpenTelemetry for Next.js server.
    // This instruments:
    // - Incoming HTTP requests (Next.js server requests, API routes)
    // - Outbound HTTP dependencies (fetch calls to backend API)
    // - Server-side rendering operations
    initAzureMonitor({
      azureMonitorExporterOptions: {
        connectionString,
      },
      resource: resourceFromAttributes({
        "service.name": "integrisight-frontend",
        "service.version": "0.1.0",
      }),
      samplingRatio: 1.0, // 100% sampling - adjust in production if needed
    });

    console.log("[OpenTelemetry] Azure Monitor instrumentation initialized for Next.js server");
  }
}
