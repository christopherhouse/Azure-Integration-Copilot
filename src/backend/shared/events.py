from datetime import UTC, datetime
from typing import Any

import aiohttp
import structlog
from azure.core.messaging import CloudEvent
from azure.eventgrid.aio import EventGridPublisherClient
from azure.identity.aio import DefaultAzureCredential
from opentelemetry.propagate import inject
from ulid import ULID

from config import settings
from shared.credential import create_credential

# Re-export the canonical event type constant for backward compatibility.
from shared.event_types import EVENT_ARTIFACT_UPLOADED as ARTIFACT_UPLOADED  # noqa: F401

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def build_cloud_event(
    *,
    event_type: str,
    subject: str,
    data: dict[str, Any],
    source: str = "/integration-copilot/api",
) -> CloudEvent:
    """Build an Azure SDK ``CloudEvent`` instance in CloudEvents v1.0 format.

    Each event receives a unique ``evt_``-prefixed ULID as its ``id`` and the
    current UTC timestamp as ``time``.

    **Distributed Tracing:**
    The current OpenTelemetry trace context is automatically injected into
    the event's extension attributes (``traceparent``, ``tracestate``) so that
    downstream consumers (workers) can continue the trace and maintain end-to-end
    correlation across the event-driven pipeline.
    """
    event = CloudEvent(
        id=f"evt_{ULID()}",
        type=event_type,
        source=source,
        subject=subject,
        data=data,
        time=datetime.now(UTC),
    )

    # Inject W3C Trace Context into CloudEvent extension attributes.
    # OpenTelemetry propagators serialize the current trace context into a
    # dict with keys like 'traceparent' and 'tracestate'. We copy these into
    # the CloudEvent extensions so downstream consumers can extract and
    # continue the trace.
    carrier: dict[str, str] = {}
    inject(carrier)
    for key, value in carrier.items():
        event.extensions[key] = value

    return event


class EventGridPublisher:
    """Wrapper around Event Grid Namespace publish API."""

    def __init__(self) -> None:
        self._client: EventGridPublisherClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> EventGridPublisherClient:
        if self._client is None:
            self._credential = create_credential()
            self._client = EventGridPublisherClient(
                endpoint=settings.event_grid_namespace_endpoint,
                credential=self._credential,
                namespace_topic=settings.event_grid_topic,
            )
        return self._client

    async def publish_event(self, event: CloudEvent) -> None:
        """Publish a single CloudEvent to the configured Event Grid topic.

        If Event Grid is not configured (empty endpoint), the event is
        silently skipped with a warning log.
        """
        if not settings.event_grid_namespace_endpoint:
            logger.warning("event_grid_not_configured", event_type=event.type)
            return

        try:
            client = await self._get_client()
            await client.send(event)
            logger.info("event_published", event_type=event.type, subject=event.subject)
        except Exception:
            logger.warning("event_publish_failed", event_type=event.type, exc_info=True)

    async def ping(self) -> bool:
        """Check connectivity to Azure Event Grid Namespace. Returns True if reachable."""
        try:
            # EventGridPublisherClient does not expose a lightweight read
            # operation, so we use aiohttp to issue a plain GET against the
            # namespace endpoint.  Any HTTP-level response (including 401/404)
            # confirms network reachability; only transport failures surface
            # as errors.
            timeout = aiohttp.ClientTimeout(total=5)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(settings.event_grid_namespace_endpoint) as resp:
                    return resp.status < 500
        except Exception:
            logger.warning("event_grid_ping_failed", exc_info=True)
            return False

    async def close(self) -> None:
        """Close the Event Grid publisher client and credential."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None


event_grid_publisher = EventGridPublisher()
