"""Unit tests for the individual ping() methods on shared service wrappers."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest


# ---------------------------------------------------------------------------
# BlobService.ping – uses get_container_properties on the artifacts container
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_blob_ping_returns_true_on_success():
    """BlobService.ping returns True when get_container_properties succeeds."""
    from shared.blob import BlobService

    service = BlobService()
    mock_container = AsyncMock()
    mock_container.get_container_properties = AsyncMock(return_value={})

    mock_client = AsyncMock()
    mock_client.get_container_client = MagicMock(return_value=mock_container)

    with patch.object(service, "_get_client", return_value=mock_client):
        result = await service.ping()

    assert result is True
    mock_client.get_container_client.assert_called_once_with("artifacts")
    mock_container.get_container_properties.assert_awaited_once()


@pytest.mark.asyncio
async def test_blob_ping_returns_false_on_exception():
    """BlobService.ping returns False when get_container_properties raises."""
    from shared.blob import BlobService

    service = BlobService()
    mock_container = AsyncMock()
    mock_container.get_container_properties = AsyncMock(side_effect=Exception("auth error"))

    mock_client = AsyncMock()
    mock_client.get_container_client = MagicMock(return_value=mock_container)

    with patch.object(service, "_get_client", return_value=mock_client):
        result = await service.ping()

    assert result is False


# ---------------------------------------------------------------------------
# EventGridPublisher.ping – uses aiohttp GET against namespace endpoint
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_event_grid_ping_returns_true_on_200():
    """EventGridPublisher.ping returns True when aiohttp GET returns 200."""
    from shared.events import EventGridPublisher

    publisher = EventGridPublisher()
    mock_response = AsyncMock()
    mock_response.status = 200

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))

    with patch("shared.events.aiohttp.ClientSession", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock())):
        result = await publisher.ping()

    assert result is True


@pytest.mark.asyncio
async def test_event_grid_ping_returns_true_on_401():
    """EventGridPublisher.ping returns True on 401 (reachable, just not authed)."""
    from shared.events import EventGridPublisher

    publisher = EventGridPublisher()
    mock_response = AsyncMock()
    mock_response.status = 401

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))

    with patch("shared.events.aiohttp.ClientSession", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock())):
        result = await publisher.ping()

    assert result is True


@pytest.mark.asyncio
async def test_event_grid_ping_returns_false_on_500():
    """EventGridPublisher.ping returns False when endpoint returns 500."""
    from shared.events import EventGridPublisher

    publisher = EventGridPublisher()
    mock_response = AsyncMock()
    mock_response.status = 500

    mock_session = AsyncMock()
    mock_session.get = MagicMock(return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_response)))

    with patch("shared.events.aiohttp.ClientSession", return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_session), __aexit__=AsyncMock())):
        result = await publisher.ping()

    assert result is False


@pytest.mark.asyncio
async def test_event_grid_ping_returns_false_on_connection_error():
    """EventGridPublisher.ping returns False when aiohttp raises a connection error."""
    from shared.events import EventGridPublisher

    publisher = EventGridPublisher()

    with patch("shared.events.aiohttp.ClientSession", side_effect=Exception("connection refused")):
        result = await publisher.ping()

    assert result is False
