import logging
import uuid
from datetime import UTC, datetime

import structlog
from azure.core.messaging import CloudEvent
from azure.core.rest import HttpRequest
from azure.eventgrid.aio import EventGridPublisherClient
from azure.identity.aio import DefaultAzureCredential

from config import settings
from shared.credential import create_credential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def build_cloud_event(
    *,
    event_type: str,
    source: str,
    subject: str,
    data: dict,
) -> CloudEvent:
    """Build a CloudEvents v1.0 envelope.

    Returns an ``azure.core.messaging.CloudEvent`` instance ready for
    publishing via ``EventGridPublisher.publish``.
    """
    return CloudEvent(
        source=source,
        type=event_type,
        subject=subject,
        data=data,
        id=f"evt_{uuid.uuid4().hex}",
        time=datetime.now(UTC),
        datacontenttype="application/json",
    )


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

    async def publish(self, event: CloudEvent) -> None:
        """Publish a CloudEvent to the configured Event Grid Namespace topic.

        If the Event Grid endpoint is not configured the call is silently
        skipped so that uploads still succeed in environments without Event
        Grid (e.g. local development).
        """
        if not settings.event_grid_namespace_endpoint:
            logger.warning("event_grid_publish_skipped", reason="endpoint not configured")
            return

        client = await self._get_client()
        await client.send(event)
        logger.info(
            "event_published",
            event_type=event.type,
            event_id=event.id,
            subject=event.subject,
        )

    async def ping(self) -> bool:
        """Check connectivity to Azure Event Grid Namespace. Returns True if reachable."""
        try:
            client = await self._get_client()
            # Use the SDK pipeline to issue a lightweight GET against the namespace
            # endpoint.  Any HTTP-level response (including 404) confirms network
            # reachability; only transport / auth failures should surface as errors.
            request = HttpRequest(method="GET", url=settings.event_grid_namespace_endpoint)
            response = await client.send_request(request)
            return response.status_code < 500
        except Exception:
            logger.warning("event_grid_ping_failed", exc_info=True, level=logging.WARNING)
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
