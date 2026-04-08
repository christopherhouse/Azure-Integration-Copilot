/**
 * Trace context management for frontend-to-backend correlation.
 *
 * Generates and manages trace IDs that flow from frontend operations to
 * backend API requests. While the frontend doesn't implement full distributed
 * tracing (per Microsoft's recommendation to avoid browser-side telemetry),
 * this lightweight approach enables correlation of user actions with backend
 * operations in Application Insights.
 */

let currentTraceId: string | null = null;

/**
 * Generate a simple trace ID (UUID v4-like).
 *
 * This is a lightweight client-side trace ID generator that produces
 * random identifiers without requiring full W3C Trace Context support.
 * The IDs are used for correlation purposes only, not full distributed
 * tracing.
 */
function generateTraceId(): string {
  return crypto.randomUUID();
}

/**
 * Get the current trace ID, generating a new one if needed.
 *
 * The trace ID persists for the lifetime of the page/session, enabling
 * correlation of multiple API calls made during a single user interaction.
 */
export function getOrCreateTraceId(): string {
  if (!currentTraceId) {
    currentTraceId = generateTraceId();
  }
  return currentTraceId;
}

/**
 * Reset the trace ID, forcing generation of a new one on next access.
 *
 * Call this when starting a new logical operation (e.g., navigating to a
 * new page or beginning a new workflow) to start a fresh correlation scope.
 */
export function resetTraceId(): void {
  currentTraceId = null;
}

/**
 * Set a specific trace ID (e.g., extracted from a server-side render).
 *
 * This allows server-rendered pages to inject a trace ID that was used
 * during SSR, maintaining correlation between server and client operations.
 */
export function setTraceId(traceId: string): void {
  currentTraceId = traceId;
}
