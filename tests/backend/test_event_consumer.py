"""Tests for the Event Grid pull-delivery consumer."""

import os
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_test_env = {
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "https://fake-eg.westus-1.eventgrid.azure.net",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from shared.event_consumer import EventGridConsumer


class TestEventGridConsumer:
    """Tests for receive / acknowledge / release operations."""

    def _make_consumer(self) -> EventGridConsumer:
        return EventGridConsumer(
            endpoint="https://fake-eg.westus-1.eventgrid.azure.net",
            namespace_topic="integration-events",
            subscription="test-sub",
        )

    @pytest.mark.asyncio
    async def test_receive_events_delegates_to_client(self):
        consumer = self._make_consumer()
        mock_client = AsyncMock()
        mock_client.receive = AsyncMock(return_value=[])
        consumer._client = mock_client
        consumer._credential = MagicMock()

        result = await consumer.receive_events(max_events=5, max_wait_time=10)

        mock_client.receive.assert_awaited_once_with(max_events=5, max_wait_time=10)
        assert result == []

    @pytest.mark.asyncio
    async def test_acknowledge_delegates_to_client(self):
        consumer = self._make_consumer()
        mock_client = AsyncMock()
        mock_client.acknowledge = AsyncMock(return_value={"succeededLockTokens": ["tok1"]})
        consumer._client = mock_client
        consumer._credential = MagicMock()

        await consumer.acknowledge(["tok1"])

        mock_client.acknowledge.assert_awaited_once_with(lock_tokens=["tok1"])

    @pytest.mark.asyncio
    async def test_acknowledge_skips_empty_list(self):
        consumer = self._make_consumer()
        mock_client = AsyncMock()
        consumer._client = mock_client
        consumer._credential = MagicMock()

        await consumer.acknowledge([])

        mock_client.acknowledge.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_release_delegates_to_client(self):
        consumer = self._make_consumer()
        mock_client = AsyncMock()
        mock_client.release = AsyncMock(return_value={"succeededLockTokens": ["tok1"]})
        consumer._client = mock_client
        consumer._credential = MagicMock()

        await consumer.release(["tok1"])

        mock_client.release.assert_awaited_once_with(lock_tokens=["tok1"])

    @pytest.mark.asyncio
    async def test_release_skips_empty_list(self):
        consumer = self._make_consumer()
        mock_client = AsyncMock()
        consumer._client = mock_client
        consumer._credential = MagicMock()

        await consumer.release([])

        mock_client.release.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_close_closes_client_and_credential(self):
        consumer = self._make_consumer()
        mock_client = AsyncMock()
        mock_credential = AsyncMock()
        consumer._client = mock_client
        consumer._credential = mock_credential

        await consumer.close()

        mock_client.close.assert_awaited_once()
        mock_credential.close.assert_awaited_once()
        assert consumer._client is None
        assert consumer._credential is None

    @pytest.mark.asyncio
    async def test_close_is_safe_when_not_initialized(self):
        consumer = self._make_consumer()
        await consumer.close()  # Should not raise
