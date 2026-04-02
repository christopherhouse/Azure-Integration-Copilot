"""Event Grid Namespace pull-delivery consumer."""

from __future__ import annotations

from typing import TYPE_CHECKING

import structlog
from azure.eventgrid.aio import EventGridConsumerClient
from azure.identity.aio import DefaultAzureCredential

from shared.credential import create_credential

if TYPE_CHECKING:
    from azure.eventgrid.models import ReceiveDetails

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class EventGridConsumer:
    """Async wrapper around :class:`EventGridConsumerClient` for pull delivery.

    The consumer binds to a single *namespace topic* and *subscription* and
    exposes thin helpers for receive / acknowledge / release operations.
    """

    def __init__(self, endpoint: str, namespace_topic: str, subscription: str) -> None:
        self._endpoint = endpoint
        self._namespace_topic = namespace_topic
        self._subscription = subscription
        self._client: EventGridConsumerClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> EventGridConsumerClient:
        if self._client is None:
            self._credential = create_credential()
            self._client = EventGridConsumerClient(
                endpoint=self._endpoint,
                credential=self._credential,
                namespace_topic=self._namespace_topic,
                subscription=self._subscription,
            )
        return self._client

    async def receive_events(
        self, *, max_events: int = 10, max_wait_time: int = 30
    ) -> list[ReceiveDetails]:
        """Pull a batch of events from the subscription.

        Returns a list of :class:`ReceiveDetails` objects.  Each item
        contains ``.event`` (a ``CloudEvent``) and
        ``.broker_properties.lock_token``.
        """
        client = await self._get_client()
        return await client.receive(max_events=max_events, max_wait_time=max_wait_time)

    async def acknowledge(self, lock_tokens: list[str]) -> None:
        """Acknowledge events so they are removed from the subscription."""
        if not lock_tokens:
            return
        client = await self._get_client()
        result = await client.acknowledge(lock_tokens=lock_tokens)
        failed = result.get("failedLockTokens") or []
        if failed:
            logger.warning("acknowledge_partial_failure", failed_count=len(failed))

    async def release(self, lock_tokens: list[str]) -> None:
        """Release events back to the subscription for redelivery."""
        if not lock_tokens:
            return
        client = await self._get_client()
        result = await client.release(lock_tokens=lock_tokens)
        failed = result.get("failedLockTokens") or []
        if failed:
            logger.warning("release_partial_failure", failed_count=len(failed))

    async def close(self) -> None:
        """Close the underlying client and credential."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None
