# Prompt — Execute Task 007: Eventing Foundation

You are an expert Python backend engineer. Execute the following task to implement the eventing infrastructure and scan-gate worker for Integration Copilot.

## Context

Read these documents before starting:

- **Task spec**: `docs/plan/tasks/007-eventing-foundation.md`
- **Eventing and processing**: `docs/plan/05-domain-eventing-and-processing.md`
- **System architecture**: `docs/plan/01-system-architecture.md`

**Prerequisites**: Tasks 002 (API foundation) and 005 (artifact domain) must be complete. The Event Grid publisher stub, Cosmos DB client, Blob Storage client, and artifact status state machine must exist.

## What You Must Do

Build the shared eventing library (publish + consume), the worker base class with pull loop and error handling, and the scan-gate passthrough worker. This is the foundation for all background processing.

### Step 1 — Event Type Constants

Create `src/backend/shared/event_types.py`:
```python
EVENT_ARTIFACT_UPLOADED = "com.integration-copilot.artifact.uploaded.v1"
EVENT_ARTIFACT_SCAN_PASSED = "com.integration-copilot.artifact.scan-passed.v1"
EVENT_ARTIFACT_SCAN_FAILED = "com.integration-copilot.artifact.scan-failed.v1"
EVENT_ARTIFACT_PARSED = "com.integration-copilot.artifact.parsed.v1"
EVENT_ARTIFACT_PARSE_FAILED = "com.integration-copilot.artifact.parse-failed.v1"
EVENT_GRAPH_UPDATED = "com.integration-copilot.graph.updated.v1"
EVENT_GRAPH_BUILD_FAILED = "com.integration-copilot.graph.build-failed.v1"
EVENT_ANALYSIS_REQUESTED = "com.integration-copilot.analysis.requested.v1"
EVENT_ANALYSIS_COMPLETED = "com.integration-copilot.analysis.completed.v1"
EVENT_ANALYSIS_FAILED = "com.integration-copilot.analysis.failed.v1"
```

### Step 2 — CloudEvents Builder

Update `src/backend/shared/events.py`:
- `build_cloud_event(event_type, source, subject, data) -> dict` — returns a CloudEvents v1.0 envelope with `specversion`, `id` (ULID with `evt_` prefix), `source`, `type`, `datacontenttype`, `time`, `subject`, `data`.
- Update the Event Grid publisher to publish CloudEvents-formatted events.

### Step 3 — Event Grid Pull Delivery Consumer

Create `src/backend/shared/event_consumer.py`:
- `EventGridConsumer` class using `azure-eventgrid` SDK with `DefaultAzureCredential`.
- Methods: `receive_events(max_events, max_wait_time)`, `acknowledge(lock_tokens)`, `release(lock_tokens)`.
- Add `azure-eventgrid` to dependencies if not present.

### Step 4 — Worker Base Class

Create `src/backend/workers/base.py`:
- `BaseWorker` class with:
  - `__init__(consumer, handler, poll_interval)` — accepts an `EventGridConsumer` and a handler.
  - `run()` — main async pull loop that calls `receive_events()`, then processes each event.
  - `_process_event(event)` — validates `tenantId` in event data, checks idempotency via `handler.is_already_processed()`, calls `handler.handle()`, acknowledges on success.
  - Error handling:
    - `TransientError` → release event for retry.
    - `PermanentError` → call `handler.handle_failure()`, acknowledge event.
    - Unexpected exceptions → release for retry.
  - Structured logging with event IDs and tenant context.
- Create `src/backend/workers/__init__.py`.

### Step 5 — Dead-Letter Handler

Create `src/backend/workers/shared/dead_letter.py`:
- `DeadLetterHandler` class that stores failed events to Blob Storage at `dead-letters/{subscriptionName}/{date}/{eventId}.json`.

### Step 6 — Scan-Gate Worker

Create `src/backend/workers/scan_gate/`:
- `handler.py` — `ScanGateHandler`:
  - `is_already_processed(event_data)` — returns True if artifact status is already past `scan_passed`.
  - `handle(event_data)` — transitions artifact `uploaded` → `scanning` → `scan_passed`, publishes `ArtifactScanPassed` event.
  - `handle_failure(event_data, error)` — transitions to `scan_failed`.
  - Has a `defender_enabled` flag (default False for MVP passthrough).
- `main.py` — entry point that creates consumer (subscription: `"malware-scan-gate"`, topic: `"integration-events"`), handler, and worker, then calls `worker.run()`.

### Step 7 — Worker Dockerfile

Create `src/backend/Dockerfile.worker` — shared Dockerfile for worker Container Apps (Python 3.13, UV install, configurable entry point).

### Step 8 — Tests

Create tests:
- `tests/backend/test_event_publisher.py` — test CloudEvents envelope structure.
- `tests/backend/test_event_consumer.py` — test receive/acknowledge/release with mocks.
- `tests/backend/test_worker_base.py` — test pull loop, idempotency, error handling.
- `tests/backend/test_scan_gate_worker.py` — test scan-gate handler status transitions and event publishing.

### Step 9 — Validation

1. Publish a test `ArtifactUploaded` event.
2. Start the scan-gate worker → verify it pulls and processes the event.
3. Check Cosmos DB: artifact status is `scan_passed`.
4. Check Event Grid: `ArtifactScanPassed` event published.
5. Replay the same event → verify idempotency (skipped).
6. Simulate a permanent error → artifact status is `scan_failed`, event acknowledged.
7. Simulate a transient error → event released for retry.
8. `uv run pytest tests/backend/test_event*.py tests/backend/test_worker*.py tests/backend/test_scan*.py -v` — all pass.

## Constraints

- Workers run as standalone Python scripts (`asyncio.run`), not inside FastAPI.
- Shared code (events, cosmos, blob) must work in both FastAPI and worker contexts.
- Events must be acknowledged or released within the lock duration (60s).
- All events must include `tenantId` in the data payload.
- Workers must validate `tenantId` before processing.
- Do not implement the parser, graph builder, analysis, or notification workers.

## Done When

- Event publishing produces valid CloudEvents to Event Grid.
- Pull delivery consumption works.
- The worker base class handles the full lifecycle: pull → validate → process → ack/release.
- The scan-gate worker transitions artifacts through the scan stage.
- Dead-letter handling stores failed events.
- All tests pass.
- The parser worker (task 008) can be built on this foundation without re-implementing event infrastructure.
