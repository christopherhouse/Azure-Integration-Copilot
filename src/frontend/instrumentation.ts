/**
 * Next.js Instrumentation Hook
 *
 * This file is automatically loaded by Next.js before the application starts.
 * It configures OpenTelemetry instrumentation for server-side code only.
 *
 * See: https://nextjs.org/docs/app/building-your-application/optimizing/instrumentation
 */

export async function register() {
  // Only instrument on the server side (Node.js)
  if (process.env.NEXT_RUNTIME === 'nodejs') {
    const connectionString = process.env.APPLICATIONINSIGHTS_CONNECTION_STRING;

    if (!connectionString) {
      console.warn('[OpenTelemetry] APPLICATIONINSIGHTS_CONNECTION_STRING not set. Telemetry will not be exported.');
      return;
    }

    // Import Azure Monitor and OTel SDK from the versions bundled with @azure/monitor-opentelemetry
    const { useAzureMonitor } = await import('@azure/monitor-opentelemetry');

    // Configure Azure Monitor OpenTelemetry with environment-based service name
    // eslint-disable-next-line react-hooks/rules-of-hooks
    useAzureMonitor({
      azureMonitorExporterOptions: {
        connectionString,
      },
      samplingRatio: 1.0, // 100% sampling - adjust in production if needed
    });

    console.log('[OpenTelemetry] Azure Monitor instrumentation initialized for frontend');
  }
}
