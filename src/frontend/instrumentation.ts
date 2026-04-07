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
    const { useAzureMonitor } = await import('@azure/monitor-opentelemetry');
    const { ATTR_SERVICE_NAME, ATTR_SERVICE_VERSION } = await import('@opentelemetry/semantic-conventions');
    const { Resource } = await import('@opentelemetry/resources');

    const connectionString = process.env.APPLICATIONINSIGHTS_CONNECTION_STRING;

    if (!connectionString) {
      console.warn('[OpenTelemetry] APPLICATIONINSIGHTS_CONNECTION_STRING not set. Telemetry will not be exported.');
      return;
    }

    // Configure Azure Monitor OpenTelemetry
    useAzureMonitor({
      azureMonitorExporterOptions: {
        connectionString,
      },
      resource: new Resource({
        [ATTR_SERVICE_NAME]: 'integrisight-frontend',
        [ATTR_SERVICE_VERSION]: '0.1.0',
      }),
      samplingRatio: 1.0, // 100% sampling - adjust in production if needed
    });

    console.log('[OpenTelemetry] Azure Monitor instrumentation initialized for frontend');
  }
}
