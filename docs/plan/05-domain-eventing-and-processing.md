# 05 — Domain: Eventing and Processing

## Goals

- Define the shared event envelope used by all events in the system.
- Define all core event types for MVP.
- Define Event Grid subscriptions and what each consumes and produces.
- Define idempotency, retry, poison, and dead-letter handling.
- Define worker responsibilities and boundaries.

## Scope

MVP: single Event Grid Namespace topic, pull delivery, six subscriptions, four worker Container Apps.

---

## Event Grid Namespace Setup

| Resource | Value |
|----------|-------|
| Namespace | `egns-integration-copilot-{env}` |
| Topic | `integration-events` |
| Schema | CloudEvents v1.0 |
| Delivery mode | Pull |
| Subscriptions | See table below |

---

## Shared Event Envelope

All events use the CloudEvents v1.0 schema with custom extension attributes.

```json
{
  "specversion": "1.0",
  "id": "evt_01HQ...",
  "source": "/integration-copilot/api",
  "type": "com.integration-copilot.artifact.uploaded.v1",
  "datacontenttype": "application/json",
  "time": "2026-03-25T14:30:00Z",
  "subject": "tenants/tn_01HQXYZ/projects/prj_01HQ/artifacts/art_01HQ",
  "data": {
    "tenantId": "tn_01HQXYZ...",
    "projectId": "prj_01HQ...",
    "artifactId": "art_01HQ...",
    "artifactType": "logic_app_workflow",
    "blobPath": "tenants/tn_01HQXYZ/projects/prj_01HQ/artifacts/art_01HQ/order-processor.json"
  }
}
```

### Envelope Rules

- `id`: Unique event ID (ULID with `evt_` prefix). Used for idempotency checks.
- `source`: Identifies the producing component (`/integration-copilot/api`, `/integration-copilot/worker-parser`, etc.).
- `type`: Fully qualified event type. Versioned with `.v1` suffix.
- `subject`: Hierarchical resource path for filtering.
- `data.tenantId`: Always present. Workers must validate this before processing.
- `data.projectId`: Present for all project-scoped events.

---

## Core Event Types

| Event Type | Producer | Description |
|------------|----------|-------------|
| `com.integration-copilot.artifact.uploaded.v1` | API | Artifact uploaded to Blob Storage |
| `com.integration-copilot.artifact.scan-passed.v1` | Scan Gate Worker | Malware scan passed (or passthrough in dev) |
| `com.integration-copilot.artifact.scan-failed.v1` | Scan Gate Worker | Malware detected |
| `com.integration-copilot.artifact.parsed.v1` | Parser Worker | Artifact successfully parsed |
| `com.integration-copilot.artifact.parse-failed.v1` | Parser Worker | Parsing failed |
| `com.integration-copilot.graph.updated.v1` | Graph Builder Worker | Graph updated with new components/edges |
| `com.integration-copilot.graph.build-failed.v1` | Graph Builder Worker | Graph build failed |
| `com.integration-copilot.analysis.requested.v1` | API | User requested an analysis |
| `com.integration-copilot.analysis.completed.v1` | Analysis Worker | Analysis completed successfully |
| `com.integration-copilot.analysis.failed.v1` | Analysis Worker | Analysis failed |

### Event Data Schemas

#### ArtifactUploaded

```json
{
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "artifactId": "art_01HQ...",
  "artifactType": "logic_app_workflow",
  "blobPath": "tenants/.../order-processor.json",
  "fileSizeBytes": 24576,
  "contentHash": "sha256:abc123..."
}
```

#### ArtifactScanPassed / ArtifactScanFailed

```json
{
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "artifactId": "art_01HQ...",
  "scanResult": "clean",
  "scannedAt": "2026-03-25T14:30:30Z"
}
```

#### ArtifactParsed

```json
{
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "artifactId": "art_01HQ...",
  "parseResultId": "pr_01HQ...",
  "componentCount": 12,
  "edgeCount": 8
}
```

#### GraphUpdated

```json
{
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "graphVersion": 4,
  "componentsUpserted": 12,
  "edgesUpserted": 8,
  "triggeredByArtifactId": "art_01HQ..."
}
```

#### AnalysisRequested

```json
{
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "analysisId": "anl_01HQ...",
  "prompt": "What is the blast radius if the Order API goes down?",
  "requestedBy": "usr_01HQABC..."
}
```

#### AnalysisCompleted

```json
{
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "analysisId": "anl_01HQ...",
  "resultSummary": "The Order API is called by 3 workflows and 2 API operations...",
  "toolCallCount": 4
}
```

---

## Subscriptions

| Subscription Name | Filters (event type prefix) | Consumer | Produces |
|-------------------|----------------------------|----------|----------|
| `malware-scan-gate` | `artifact.uploaded` | Scan Gate Worker (or passthrough) | `artifact.scan-passed` or `artifact.scan-failed` |
| `artifact-parser` | `artifact.scan-passed` | Parser Worker | `artifact.parsed` or `artifact.parse-failed` |
| `graph-builder` | `artifact.parsed` | Graph Builder Worker | `graph.updated` or `graph.build-failed` |
| `agent-context` | `graph.updated` | (Future) Context refresh worker | — (MVP: no-op, reserved) |
| `analysis-execution` | `analysis.requested` | Analysis Worker | `analysis.completed` or `analysis.failed` |
| `notification` | All terminal events: `artifact.scan-passed`, `artifact.scan-failed`, `artifact.parsed`, `artifact.parse-failed`, `graph.updated`, `graph.build-failed`, `analysis.completed`, `analysis.failed` | Notification Worker | Web PubSub messages |

### Subscription Filter Configuration

Each subscription uses an Event Grid subject prefix or event type filter to route relevant events.

```
malware-scan-gate:
  filter: type prefix "com.integration-copilot.artifact.uploaded"

artifact-parser:
  filter: type prefix "com.integration-copilot.artifact.scan-passed"

graph-builder:
  filter: type prefix "com.integration-copilot.artifact.parsed"

analysis-execution:
  filter: type prefix "com.integration-copilot.analysis.requested"

notification:
  filter: type prefix matches any of the terminal event types (OR filter)
```

---

## Worker Responsibilities

| Worker App | Container App Name | Subscriptions Consumed | Core Responsibility |
|-----------|-------------------|----------------------|---------------------|
| **Scan Gate Worker** | `worker-scan-gate` | `malware-scan-gate` | Check Defender for Storage result (or passthrough). Transition artifact status. Publish scan result event. |
| **Parser Worker** | `worker-parser` | `artifact-parser` | Download raw artifact from Blob. Determine type. Run parser. Store parse result. Transition artifact status. Publish parse result event. |
| **Graph Builder Worker** | `worker-graph` | `graph-builder` | Load parse result. Upsert components and edges. Update graph version. Publish graph updated event. |
| **Analysis Worker** | `worker-analysis` | `analysis-execution` | Load project context. Invoke Foundry Agent Service. Store analysis result. Publish analysis completed event. |
| **Notification Worker** | `worker-notification` | `notification` | Receive terminal events. Format notification. Send to Web PubSub group. |

### Worker Boundaries

- Workers are **stateless**. All state is in Cosmos DB or Blob Storage.
- Workers **do not call the API**. They read/write directly to Cosmos DB and Blob Storage using managed identities.
- Workers **always validate** `tenantId` from the event data before processing.
- Workers **publish events** back to the same Event Grid topic for downstream consumers.
- Workers **must be idempotent** (see below).

---

## Idempotency

### Event ID Tracking

Each worker maintains an idempotency check:

1. Before processing an event, check if `eventId` has been processed (stored in Cosmos DB or tracked via artifact status).
2. If already processed, acknowledge the event without re-processing.
3. If not processed, process the event, update status, then acknowledge.

### Practical Approach for MVP

- **Parser Worker**: Check if artifact status is already `parsed` or beyond. If so, skip.
- **Graph Builder Worker**: The graph upsert is inherently idempotent (deterministic component IDs). Re-processing produces the same graph.
- **Analysis Worker**: Check if analysis status is already `completed`. If so, skip.
- **Notification Worker**: Notifications are best-effort and idempotent (sending the same notification twice is acceptable).

---

## Retry, Poison, and Dead-Letter Handling

### Retry Strategy

| Setting | Value |
|---------|-------|
| Max delivery attempts | 5 |
| Retry delay | Exponential backoff: 10s, 30s, 60s, 120s, 300s |
| Lock duration | 60 seconds (for pull delivery) |

### Poison Event Handling

After max delivery attempts, the event is moved to a dead-letter destination.

### Dead-Letter

| Setting | Value |
|---------|-------|
| Dead-letter destination | Blob Storage container: `dead-letters/{subscriptionName}/{date}/{eventId}.json` |
| Retention | 30 days |
| Alerting | Application Insights alert on dead-letter blob creation |

### Worker Error Handling

```python
async def process_event(event: CloudEvent):
    try:
        # Validate tenant
        # Process event
        # Update status
        # Publish downstream event
        # Acknowledge event
        await acknowledge(event)
    except TransientError:
        # Do not acknowledge; event will be retried after lock expires
        logger.warning("Transient error, will retry", event_id=event.id)
        raise
    except PermanentError as e:
        # Update artifact/analysis status to failed
        # Publish failure event
        # Acknowledge event (do not retry)
        await update_status_to_failed(event, error=e)
        await publish_failure_event(event, error=e)
        await acknowledge(event)
    except Exception as e:
        # Unexpected error; do not acknowledge; let retry/dead-letter handle it
        logger.error("Unexpected error", event_id=event.id, error=str(e))
        raise
```

---

## Processing Flow Summary

```
API publishes ArtifactUploaded
  │
  ├─► malware-scan-gate subscription
  │     └─► Scan Gate Worker
  │           ├─ scan_passed → publishes ArtifactScanPassed
  │           └─ scan_failed → publishes ArtifactScanFailed ──► notification subscription
  │
  ├─► artifact-parser subscription (receives ArtifactScanPassed)
  │     └─► Parser Worker
  │           ├─ parsed → publishes ArtifactParsed
  │           └─ parse_failed → publishes ArtifactParseFailed ──► notification subscription
  │
  ├─► graph-builder subscription (receives ArtifactParsed)
  │     └─► Graph Builder Worker
  │           ├─ graph_built → publishes GraphUpdated ──► notification subscription
  │           └─ graph_failed → publishes GraphBuildFailed ──► notification subscription
  │
  └─► (analysis flow is separate, triggered by API)

API publishes AnalysisRequested
  │
  ├─► analysis-execution subscription
  │     └─► Analysis Worker
  │           ├─ completed → publishes AnalysisCompleted ──► notification subscription
  │           └─ failed → publishes AnalysisFailed ──► notification subscription
  │
  └─► notification subscription (receives all terminal events)
        └─► Notification Worker → Web PubSub
```

---

## Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| Event schema | CloudEvents v1.0 | Industry standard, Event Grid native support |
| Topic count | Single topic | Sufficient for MVP; subscriptions handle routing |
| Pull delivery | Workers pull from subscriptions | VNet-friendly, natural backpressure, KEDA scaling |
| Dead-letter | Blob Storage | Cheap, durable, queryable for debugging |
| Idempotency | Status-based checks + deterministic IDs | Practical for MVP; avoids separate idempotency store |

## Assumptions

- Event Grid Namespace pull delivery supports CloudEvents v1.0 filtering.
- KEDA Event Grid scaler is available for Container Apps.
- Single-topic throughput is sufficient for MVP (< 1000 events/minute).

## Constraints

- All events must include `tenantId` in the data payload.
- Workers must never process an event without validating tenant scope.
- Events are versioned (`.v1` suffix) to support future schema evolution.

## Open Questions

| # | Question |
|---|----------|
| 1 | Should the `agent-context` subscription be implemented as a no-op in MVP or omitted entirely? (Proposed: create subscription, implement as no-op) |
| 2 | What KEDA scaler settings are appropriate for Event Grid Namespace pull delivery? |
