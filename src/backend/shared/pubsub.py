"""Shared Web PubSub client wrapper for worker processes.

Workers use this module to send messages to Web PubSub groups.  The API
backend uses :mod:`domains.realtime.service` instead (which also handles
token negotiation).
"""

from __future__ import annotations

import structlog
from azure.identity.aio import DefaultAzureCredential
from azure.messaging.webpubsubservice.aio import WebPubSubServiceClient

from shared.credential import create_credential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_NOTIFICATION_HUB = "notifications"


class PubSubService:
    """Thin async wrapper for sending Web PubSub messages from workers."""

    def __init__(self, endpoint: str) -> None:
        self._endpoint = endpoint
        self._client: WebPubSubServiceClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> WebPubSubServiceClient:
        if self._client is None:
            self._credential = create_credential()
            self._client = WebPubSubServiceClient(
                endpoint=self._endpoint,
                hub=_NOTIFICATION_HUB,
                credential=self._credential,
            )
        return self._client

    async def send_to_group(self, group: str, data: dict) -> None:
        """Send a JSON message to a Web PubSub group."""
        if not self._endpoint:
            logger.warning("pubsub_not_configured")
            return
        try:
            client = await self._get_client()
            await client.send_to_group(
                group=group,
                message=data,
                content_type="application/json",
            )
        except Exception:
            logger.warning("pubsub_send_failed", group=group, exc_info=True)

    async def close(self) -> None:
        """Close the client and credential."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None
