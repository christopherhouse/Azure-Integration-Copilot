"""Realtime service — Web PubSub token generation."""

from __future__ import annotations

import structlog
from azure.identity.aio import DefaultAzureCredential
from azure.messaging.webpubsubservice.aio import WebPubSubServiceClient

from config import settings
from shared.credential import create_credential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Hub used for realtime notifications to clients.
_NOTIFICATION_HUB = "notifications"


class RealtimeService:
    """Generates Web PubSub client access tokens for frontend connections."""

    def __init__(self) -> None:
        self._client: WebPubSubServiceClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> WebPubSubServiceClient:
        if self._client is None:
            self._credential = create_credential()
            self._client = WebPubSubServiceClient(
                endpoint=settings.web_pubsub_endpoint,
                hub=_NOTIFICATION_HUB,
                credential=self._credential,
            )
        return self._client

    async def generate_client_token(
        self,
        user_id: str,
        groups: list[str] | None = None,
    ) -> dict:
        """Generate a client access token for Web PubSub.

        Returns a dict with ``url`` (the WebSocket URL with token).
        """
        client = await self._get_client()
        token = await client.get_client_access_token(
            user_id=user_id,
            groups=groups or [],
        )
        return {"url": token["url"]}

    async def send_to_group(self, group: str, data: dict) -> None:
        """Send a JSON message to a Web PubSub group."""
        client = await self._get_client()
        await client.send_to_group(
            group=group,
            message=data,
            content_type="application/json",
        )

    async def close(self) -> None:
        """Close the client and credential."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None


realtime_service = RealtimeService()
