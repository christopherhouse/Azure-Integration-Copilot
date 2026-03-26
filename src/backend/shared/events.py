import structlog
from azure.eventgrid.aio import EventGridPublisherClient
from azure.identity.aio import DefaultAzureCredential

from config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class EventGridPublisher:
    """Wrapper around Event Grid Namespace publish API."""

    def __init__(self) -> None:
        self._client: EventGridPublisherClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> EventGridPublisherClient:
        if self._client is None:
            self._credential = DefaultAzureCredential()
            self._client = EventGridPublisherClient(
                endpoint=settings.event_grid_namespace_endpoint,
                credential=self._credential,
            )
        return self._client

    async def close(self) -> None:
        """Close the Event Grid publisher client and credential."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None


event_grid_publisher = EventGridPublisher()
