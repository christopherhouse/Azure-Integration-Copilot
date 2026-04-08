# OpenTelemetry Distributed Tracing

This document describes the end-to-end distributed tracing implementation across the Integrisight.ai platform using OpenTelemetry and Azure Monitor Application Insights.

## Overview

The platform implements comprehensive distributed tracing that flows correlation IDs and trace context through all three tiers:

1. **Frontend (Browser & Next.js Server)** → 2. **Backend API** → 3. **Workers** → 4. **Downstream Workers**

This enables complete observability of user actions from browser through asynchronous worker pipelines.

## Architecture

### Phase 1: Backend-to-Worker Correlation ✅

**Problem:** Events published to Azure Event Grid Namespace did not carry trace context, causing worker traces to be disconnected from the API requests that triggered them.

**Solution:** W3C Trace Context propagation via CloudEvent extension attributes.

#### Implementation

**Publishing (API → Event Grid):**
- `src/backend/shared/events.py`: `build_cloud_event()` injects current trace context into CloudEvent extensions
- Uses OpenTelemetry's `inject()` propagator to serialize `traceparent` and `tracestate` headers
- Extensions flow through Event Grid with the event payload

**Consuming (Event Grid → Workers):**
- `src/backend/workers/base.py`: `_process_event()` extracts trace context from CloudEvent extensions
- Uses OpenTelemetry's `extract()` propagator to deserialize and set as parent context
- Worker processing span becomes a child of the original API request span

#### Example Flow
```
API POST /api/v1/artifacts/upload
  └─ trace_id: abc123
     └─ publishes ArtifactUploaded event with extensions['traceparent'] = "00-abc123-..."
        └─ Worker receives event and extracts traceparent
           └─ Worker span continues trace abc123 as child
```

### Phase 2: Frontend-to-Backend Correlation ✅

**Problem:** Frontend fetch calls did not propagate any correlation information to backend API, making it impossible to link user actions to backend operations.

**Solution:** Custom trace ID header + Next.js server-side instrumentation.

#### Implementation

**Client-Side Trace ID:**
- `src/frontend/src/lib/trace.ts`: Lightweight trace ID generator (UUID v4)
- Persists for page/session lifetime to correlate multiple API calls
- `src/frontend/src/lib/api.ts`: Automatically includes `X-Trace-ID` header in all API calls

**Backend Extraction:**
- `src/backend/middleware/auth.py`: Extracts `X-Trace-ID` header
- Sets as span attribute (`frontend.trace_id`) on current request span
- Sets as OpenTelemetry baggage to propagate to all child spans/workers
- Appears in all log entries and traces for correlation

**Next.js Server-Side Instrumentation:**
- `src/frontend/src/instrumentation.ts`: Azure Monitor OpenTelemetry distro for Next.js server
- Automatically instruments server-side rendering, API routes, and middleware
- Propagates W3C traceparent headers to backend API calls made server-side

#### Example Flow
```
Browser generates trace_id: xyz789
  └─ fetch("/api/v1/projects") with X-Trace-ID: xyz789
     └─ Backend API receives request
        └─ Span attribute: frontend.trace_id = xyz789
        └─ Baggage: frontend.trace_id = xyz789
           └─ All child spans inherit baggage
           └─ All log entries include frontend.trace_id
```

### Phase 3: Full Distributed Tracing ✅

**Problem:** Browser-side operations (page views, clicks, exceptions) are not captured or correlated with backend traces.

**Solution:** Application Insights browser SDK with W3C Trace Context injection, enabled by default.

#### Implementation

**Browser SDK (auto-enabled):**
- `src/frontend/src/lib/appinsights.ts`: Application Insights browser client
- `src/frontend/src/components/app-insights-telemetry.tsx`: Client component that initializes the SDK on mount
- Automatically tracks page views, AJAX/fetch calls, exceptions, performance
- Injects W3C `traceparent` headers into all outbound requests
- Creates true end-to-end traces from browser → API → workers
- Rendered in root layout (`src/frontend/src/app/layout.tsx`)

**Configuration:**
- `src/frontend/src/types/runtime-config.d.ts`: Type definitions for connection string
- `src/frontend/src/components/runtime-config.tsx`: Injects connection string at request time
- Connection string read from `APPLICATIONINSIGHTS_CONNECTION_STRING` env var

**Trade-offs:**
- ✅ Full observability from browser to workers
- ✅ Automatic exception and performance tracking
- ⚠️ ~50KB added to client bundle (gzipped)
- ⚠️ Client IP addresses and session data sent to Azure

#### Example Flow
```
User clicks button in browser
  └─ AppInsights creates trace_id: def456
     └─ fetch("/api/v1/artifacts") with traceparent: "00-def456-..."
        └─ Backend API receives and continues trace def456
           └─ publishes event with traceparent
              └─ Worker continues trace def456
                 └─ Single trace from browser click → worker completion
```

## Configuration

### Environment Variables

**Backend (API & Workers):**
```bash
APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=...;IngestionEndpoint=https://..."
```

**Frontend (Next.js Server):**
```bash
APPLICATIONINSIGHTS_CONNECTION_STRING="InstrumentationKey=...;IngestionEndpoint=https://..."
```

**Frontend (Browser - Phase 3 only):**
- Connection string is injected via RuntimeConfig component at request time
- Same `APPLICATIONINSIGHTS_CONNECTION_STRING` env var as Next.js server

### Next.js Configuration

The `instrumentation.ts` file is automatically loaded by Next.js 16+ when placed in the `src/` folder (for projects using src directory structure) or in the project root. No additional configuration in `next.config.ts` is required.

### Usage in React Components (Phase 3)

The browser SDK is initialized automatically via the `<AppInsightsTelemetry />` component
in the root layout. No manual setup is required. The connection string is read from
`window.__RUNTIME_CONFIG__.applicationInsightsConnectionString`, which is injected by the
`<RuntimeConfig />` server component.

To access the Application Insights instance for custom events:
```typescript
import { getAppInsights } from "@/lib/appinsights";

const ai = getAppInsights();
ai?.trackEvent({ name: "custom_event", properties: { ... } });
```

## Observability Features

### Application Insights Correlation

All traces appear in Application Insights with:
- **End-to-end transaction view:** Single trace from browser → API → workers
- **Dependency tracking:** HTTP calls, database queries, Event Grid publishes
- **Exception tracking:** Errors correlated with the requests that caused them
- **Performance metrics:** Request durations, dependency latencies

### Log Correlation

All structured logs include:
- `trace_id`: OpenTelemetry trace ID (flows through entire pipeline)
- `span_id`: Current operation span ID
- `frontend.trace_id`: (when available) Browser-generated correlation ID from `X-Trace-ID` header

### Custom Queries

**Find all operations for a frontend trace ID:**
```kql
union requests, dependencies, traces
| where customDimensions.frontend_trace_id == "xyz789"
| order by timestamp asc
```

**Find complete trace from browser click to worker completion:**
```kql
requests
| where operation_Id == "def456"  // AppInsights trace ID
| union (dependencies | where operation_Id == "def456")
| union (traces | where operation_Id == "def456")
| order by timestamp asc
```

## Testing

### Phase 1: Backend-to-Worker

1. Upload an artifact via API
2. Check Application Insights for the request trace
3. Verify worker spans appear as children of the upload request
4. Confirm `trace_id` matches across API logs and worker logs

### Phase 2: Frontend-to-Backend

1. Make an API call from browser
2. Check Network tab for `X-Trace-ID` header
3. Check Application Insights for backend request
4. Verify `frontend.trace_id` custom dimension matches header value
5. Confirm trace ID appears in backend logs

### Phase 3: Browser-to-Workers

1. Click a button or navigate in the browser
2. Check Application Insights for browser page view
3. Follow dependency chain through API requests
4. Verify worker spans appear as part of same trace
5. Confirm single `operation_Id` spans from browser → workers

## Maintenance

### Updating Dependencies

**Backend:**
```bash
cd src/backend
uv add opentelemetry-api@latest opentelemetry-sdk@latest
uv add azure-monitor-opentelemetry@latest
```

**Frontend:**
```bash
cd src/frontend
npm install @azure/monitor-opentelemetry@latest
npm install @microsoft/applicationinsights-web@latest
npm install @microsoft/applicationinsights-react-js@latest
```

### Disabling Browser Telemetry

To disable Phase 3 (browser SDK) while keeping Phases 1 & 2:

1. Remove or comment out `<AppInsightsTelemetry />` in `src/frontend/src/app/layout.tsx`
2. Connection string will still be available for server-side instrumentation
3. `X-Trace-ID` header will still provide lightweight correlation

## Best Practices

1. **Use baggage sparingly:** Only add high-value correlation IDs (like `frontend.trace_id`)
2. **Filter health checks:** `HealthCheckHeadFilter` in `src/backend/shared/logging.py` suppresses noisy HEAD probes
3. **Sampling (future):** For high-traffic scenarios, configure trace sampling to reduce ingestion costs
4. **Sensitive data:** Never include PII or secrets in span attributes or baggage

## Resources

- [OpenTelemetry Python](https://opentelemetry.io/docs/languages/python/)
- [Azure Monitor OpenTelemetry](https://learn.microsoft.com/azure/azure-monitor/app/opentelemetry-enable?tabs=python)
- [W3C Trace Context](https://www.w3.org/TR/trace-context/)
- [CloudEvents Distributed Tracing](https://github.com/cloudevents/spec/blob/main/cloudevents/extensions/distributed-tracing.md)
- [Application Insights JavaScript SDK](https://learn.microsoft.com/azure/azure-monitor/app/javascript)
