import structlog
from azure.identity.aio import DefaultAzureCredential
from azure.messaging.webpubsubservice.aio import WebPubSubServiceClient

from config import settings
from shared.credential import create_credential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Hub name used exclusively for the health-check probe.
_HEALTH_CHECK_HUB = "health"


class WebPubSubService:
    """Async wrapper around Azure Web PubSub service client."""

    def __init__(self) -> None:
        self._client: WebPubSubServiceClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> WebPubSubServiceClient:
        if self._client is None:
            self._credential = create_credential()
            self._client = WebPubSubServiceClient(
                endpoint=settings.web_pubsub_endpoint,
                hub=_HEALTH_CHECK_HUB,
                credential=self._credential,
            )
        return self._client

    async def ping(self) -> bool:
        """Check connectivity to Azure Web PubSub. Returns True if reachable."""
        try:
            client = await self._get_client()
            # get_client_access_token is a lightweight server-side call that
            # exercises authentication and network connectivity without
            # side-effects on connected clients.
            await client.get_client_access_token()
            return True
        except Exception:
            logger.warning("web_pubsub_ping_failed", exc_info=True)
            return False

    async def close(self) -> None:
        """Close the Web PubSub client and credential."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None


web_pubsub_service = WebPubSubService()
