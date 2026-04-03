# Task 007 — Eventing Foundation

## Title

Implement the Event Grid pull delivery infrastructure, worker base class, scan-gate worker, and dead-letter handling.

## Objective

Build the shared eventing library (publish + consume), the worker base class with pull loop, idempotency, and error handling, and the first worker (scan-gate passthrough). After this task, the event-driven processing pipeline is operational and subsequent workers can be built on the same foundation.

## Why This Task Exists

The async processing pipeline (scan → parse → graph → analysis → notification) is the backbone of Integrisight.ai. Every worker needs to: pull events, validate tenant scope, process idempotently, handle errors, publish downstream events, and manage dead-letters. Building this once as a shared foundation prevents duplication and inconsistency across workers.

## In Scope

- Event Grid Namespace publisher (update from task 002 stub to full CloudEvents support)
- Event Grid Namespace pull delivery consumer
- CloudEvents v1.0 envelope builder and parser
- Worker base class:
  - Pull loop with configurable interval
  - Event acknowledgment
  - Idempotency checking (status-based)
  - Error handling (transient vs. permanent)
  - Structured logging with tenant context
- Scan-gate worker (passthrough for MVP):
  - Consumes `ArtifactUploaded` events
  - Transitions artifact status: `uploaded` → `scanning` → `scan_passed`
  - Publishes `ArtifactScanPassed` event
  - Configuration flag for real Defender integration (future)
- Dead-letter handling (failed events to Blob Storage)
- Event Grid topic and subscription configuration documentation
- Worker Container App entry point pattern
- Shared event type constants

## Out of Scope

- Parser worker (task 008)
- Graph builder worker (task 009)
- Analysis worker (task 010)
- Notification worker (task 010)
- Real Defender for Storage integration (architecture supports it; MVP is passthrough)
- KEDA scaler configuration (Terraform/infra concern)

## Dependencies

- **Task 002** (API foundation): Event Grid publisher wrapper, Cosmos DB client, Blob Storage client.
- **Task 005** (projects/artifacts domain): Artifact status state machine, artifact repository.

## Files/Directories Expected to Be Created or Modified

```
src/backend/
├── shared/
│   ├── events.py                  # Updated: full CloudEvents builder, Event Grid publisher
│   ├── event_types.py             # New: all event type constants and data schemas
│   └── event_consumer.py          # New: Event Grid pull delivery consumer
├── workers/
│   ├── __init__.py
│   ├── base.py                    # Worker base class (pull loop, error handling)
│   ├── scan_gate/
│   │   ├── __init__.py
│   │   ├── main.py                # Entry point for scan-gate worker
│   │   └── handler.py             # Scan-gate event handler
│   └── shared/
│       ├── __init__.py
│       └── dead_letter.py         # Dead-letter storage handler
├── Dockerfile.worker              # Worker Dockerfile (shared)
tests/backend/
├── test_event_publisher.py
├── test_event_consumer.py
├── test_worker_base.py
└── test_scan_gate_worker.py
```

## Implementation Notes

### CloudEvents Envelope Builder

```python
# shared/events.py
from datetime import datetime, timezone
import uuid

def build_cloud_event(
    event_type: str,
    source: str,
    subject: str,
    data: dict,
) -> dict:
    return {
        "specversion": "1.0",
        "id": f"evt_{ulid()}",
        "source": source,
        "type": event_type,
        "datacontenttype": "application/json",
        "time": datetime.now(timezone.utc).isoformat(),
        "subject": subject,
        "data": data,
    }
```

### Event Type Constants

```python
# shared/event_types.py
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

### Event Grid Pull Delivery Consumer

```python
# shared/event_consumer.py
from azure.eventgrid import EventGridConsumerClient
from azure.identity import DefaultAzureCredential

class EventGridConsumer:
    def __init__(self, endpoint: str, subscription_name: str, topic_name: str):
        self.client = EventGridConsumerClient(
            endpoint=endpoint,
            credential=DefaultAzureCredential(),
        )
        self.subscription_name = subscription_name
        self.topic_name = topic_name

    async def receive_events(self, max_events: int = 10, max_wait_time: int = 30) -> list:
        """Pull events from the subscription."""
        result = await self.client.receive(
            topic_name=self.topic_name,
            subscription_name=self.subscription_name,
            max_events=max_events,
            max_wait_time=max_wait_time,
        )
        return result.value

    async def acknowledge(self, lock_tokens: list[str]):
        """Acknowledge processed events."""
        await self.client.acknowledge(
            topic_name=self.topic_name,
            subscription_name=self.subscription_name,
            lock_tokens=lock_tokens,
        )

    async def release(self, lock_tokens: list[str]):
        """Release events back to the subscription for retry."""
        await self.client.release(
            topic_name=self.topic_name,
            subscription_name=self.subscription_name,
            lock_tokens=lock_tokens,
        )
```

### Worker Base Class

```python
# workers/base.py
import asyncio
import structlog

class BaseWorker:
    def __init__(self, consumer: EventGridConsumer, handler, poll_interval: int = 5):
        self.consumer = consumer
        self.handler = handler
        self.poll_interval = poll_interval
        self.logger = structlog.get_logger()
        self.running = True

    async def run(self):
        """Main pull loop."""
        self.logger.info("Worker started", subscription=self.consumer.subscription_name)
        while self.running:
            try:
                events = await self.consumer.receive_events()
                for event in events:
                    await self._process_event(event)
            except Exception as e:
                self.logger.error("Pull loop error", error=str(e))
                await asyncio.sleep(self.poll_interval)

    async def _process_event(self, event):
        event_data = event.event.data
        lock_token = event.broker_properties.lock_token
        
        try:
            # Validate tenant context
            tenant_id = event_data.get("tenantId")
            if not tenant_id:
                self.logger.error("Event missing tenantId", event_id=event.event.id)
                await self.consumer.acknowledge([lock_token])
                return

            # Check idempotency (subclass implements)
            if await self.handler.is_already_processed(event_data):
                self.logger.info("Event already processed, skipping", event_id=event.event.id)
                await self.consumer.acknowledge([lock_token])
                return

            # Process
            await self.handler.handle(event_data)
            await self.consumer.acknowledge([lock_token])

        except TransientError:
            self.logger.warning("Transient error, releasing for retry", event_id=event.event.id)
            await self.consumer.release([lock_token])

        except PermanentError as e:
            self.logger.error("Permanent error", event_id=event.event.id, error=str(e))
            await self.handler.handle_failure(event_data, error=e)
            await self.consumer.acknowledge([lock_token])

        except Exception as e:
            self.logger.error("Unexpected error, releasing for retry", event_id=event.event.id, error=str(e))
            await self.consumer.release([lock_token])
```

### Scan-Gate Worker

```python
# workers/scan_gate/handler.py
class ScanGateHandler:
    def __init__(self, artifact_repo, event_publisher, defender_enabled: bool = False):
        self.artifact_repo = artifact_repo
        self.event_publisher = event_publisher
        self.defender_enabled = defender_enabled

    async def is_already_processed(self, event_data: dict) -> bool:
        artifact = await self.artifact_repo.get_by_id(
            event_data["tenantId"], event_data["artifactId"]
        )
        return artifact and artifact["status"] in ("scan_passed", "parsed", "graph_built")

    async def handle(self, event_data: dict):
        artifact_id = event_data["artifactId"]
        tenant_id = event_data["tenantId"]
        
        # Transition to scanning
        await self.artifact_repo.update_status(tenant_id, artifact_id, "scanning")
        
        if self.defender_enabled:
            # Future: check Defender for Storage scan result
            pass
        
        # Passthrough: immediately mark as scan_passed
        await self.artifact_repo.update_status(tenant_id, artifact_id, "scan_passed")
        
        # Publish scan passed event
        await self.event_publisher.publish(build_cloud_event(
            event_type=EVENT_ARTIFACT_SCAN_PASSED,
            source="/integration-copilot/worker-scan-gate",
            subject=f"tenants/{tenant_id}/projects/{event_data['projectId']}/artifacts/{artifact_id}",
            data={
                "tenantId": tenant_id,
                "projectId": event_data["projectId"],
                "artifactId": artifact_id,
                "scanResult": "clean",
                "scannedAt": datetime.now(timezone.utc).isoformat(),
            },
        ))

    async def handle_failure(self, event_data: dict, error: Exception):
        await self.artifact_repo.update_status(
            event_data["tenantId"], event_data["artifactId"], "scan_failed",
            error={"code": "SCAN_ERROR", "message": str(error)}
        )
```

### Dead-Letter Handler

```python
# workers/shared/dead_letter.py
class DeadLetterHandler:
    def __init__(self, blob_service):
        self.blob_service = blob_service

    async def store(self, subscription_name: str, event: dict):
        date = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        event_id = event.get("id", "unknown")
        path = f"dead-letters/{subscription_name}/{date}/{event_id}.json"
        await self.blob_service.upload(path, json.dumps(event))
```

### Worker Entry Point

```python
# workers/scan_gate/main.py
import asyncio
from workers.base import BaseWorker
from workers.scan_gate.handler import ScanGateHandler

async def main():
    consumer = EventGridConsumer(
        endpoint=settings.event_grid_namespace_endpoint,
        subscription_name="malware-scan-gate",
        topic_name="integration-events",
    )
    handler = ScanGateHandler(
        artifact_repo=artifact_repo,
        event_publisher=event_publisher,
        defender_enabled=settings.defender_scan_enabled,
    )
    worker = BaseWorker(consumer=consumer, handler=handler)
    await worker.run()

if __name__ == "__main__":
    asyncio.run(main())
```

## Acceptance Criteria

- [ ] CloudEvents envelope is correctly structured (specversion, id, type, source, data)
- [ ] Events can be published to Event Grid Namespace topic
- [ ] Events can be pulled from Event Grid Namespace subscriptions
- [ ] Worker base class runs a pull loop and processes events
- [ ] Scan-gate worker transitions artifact status: `uploaded` → `scanning` → `scan_passed`
- [ ] Scan-gate worker publishes `ArtifactScanPassed` event
- [ ] Idempotency: re-processing an already-scanned artifact is a no-op
- [ ] Transient errors are released for retry
- [ ] Permanent errors update status to failed and acknowledge
- [ ] Dead-letter handler stores failed events in Blob Storage
- [ ] All events include `tenantId` in the data payload
- [ ] Workers validate `tenantId` before processing
- [ ] Structured logs include event IDs and tenant context

## Definition of Done

- The eventing infrastructure is operational (publish + consume).
- The worker base class is reusable for all subsequent workers.
- The scan-gate worker completes the first stage of the processing pipeline.
- Dead-letter handling is in place.
- The parser worker task (008) can build on this foundation without re-implementing pull delivery or error handling.

## Risks / Gotchas

- **Event Grid SDK**: Ensure the correct Azure SDK package for Event Grid Namespaces pull delivery (`azure-eventgrid`). The pull delivery API may be in a newer version of the SDK.
- **Lock tokens**: Events must be acknowledged or released within the lock duration (60s default). Long processing may cause lock expiry.
- **Async context**: Workers run as standalone Python scripts (`asyncio.run`), not inside FastAPI. Shared code must work in both contexts.
- **Local development**: Consider a mock Event Grid consumer for local testing that reads from an in-memory queue.

## Suggested Validation Steps

1. Publish a test event using the Event Grid publisher.
2. Start the scan-gate worker and verify it pulls and processes the event.
3. Check Cosmos DB: artifact status should be `scan_passed`.
4. Check Event Grid: `ArtifactScanPassed` event should be published.
5. Re-run the worker with the same event → verify idempotency (no re-processing).
6. Simulate a permanent error → verify artifact status is `scan_failed` and event is acknowledged.
7. Simulate a transient error → verify event is released for retry.
8. Run tests: `uv run pytest tests/backend/test_event*.py tests/backend/test_worker*.py tests/backend/test_scan*.py -v`
