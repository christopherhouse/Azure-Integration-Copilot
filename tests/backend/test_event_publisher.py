"""Tests for CloudEvents builder and publisher."""

import os
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_test_env = {
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "https://fake-eg.westus-1.eventgrid.azure.net",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from shared.event_types import EVENT_ARTIFACT_UPLOADED
    from shared.events import build_cloud_event


class TestBuildCloudEvent:
    """Tests for the ``build_cloud_event`` helper."""

    def test_returns_cloud_event_with_required_fields(self):
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            subject="tenants/t1/projects/p1/artifacts/a1",
            data={"tenantId": "t1", "artifactId": "a1"},
        )
        assert event.type == EVENT_ARTIFACT_UPLOADED
        assert event.subject == "tenants/t1/projects/p1/artifacts/a1"
        assert event.data == {"tenantId": "t1", "artifactId": "a1"}
        assert event.source == "/integration-copilot/api"

    def test_event_id_has_evt_prefix(self):
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            subject="test",
            data={"tenantId": "t1"},
        )
        assert event.id.startswith("evt_")

    def test_event_ids_are_unique(self):
        ids = set()
        for _ in range(100):
            event = build_cloud_event(
                event_type=EVENT_ARTIFACT_UPLOADED,
                subject="test",
                data={"tenantId": "t1"},
            )
            ids.add(event.id)
        assert len(ids) == 100

    def test_event_time_is_set(self):
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            subject="test",
            data={"tenantId": "t1"},
        )
        assert event.time is not None
        assert isinstance(event.time, datetime)

    def test_custom_source(self):
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            subject="test",
            data={"tenantId": "t1"},
            source="/integration-copilot/worker/scan-gate",
        )
        assert event.source == "/integration-copilot/worker/scan-gate"

    def test_specversion_is_1_0(self):
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            subject="test",
            data={"tenantId": "t1"},
        )
        assert event.specversion == "1.0"


class TestEventGridPublisher:
    """Tests for the EventGridPublisher class."""

    @pytest.mark.asyncio
    async def test_publish_skips_when_endpoint_empty(self):
        with patch.dict(os.environ, {"EVENT_GRID_NAMESPACE_ENDPOINT": ""}):
            # Re-import to pick up new settings
            from shared.events import EventGridPublisher

            publisher = EventGridPublisher()
            event = build_cloud_event(
                event_type=EVENT_ARTIFACT_UPLOADED,
                subject="test",
                data={"tenantId": "t1"},
            )
            # Should not raise
            await publisher.publish_event(event)

    @pytest.mark.asyncio
    async def test_publish_calls_client_send(self):
        from shared.events import EventGridPublisher

        publisher = EventGridPublisher()
        mock_client = AsyncMock()
        publisher._client = mock_client
        publisher._credential = MagicMock()

        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            subject="test",
            data={"tenantId": "t1"},
        )
        with patch("shared.events.settings") as mock_settings:
            mock_settings.event_grid_namespace_endpoint = "https://fake-eg.example.net"
            mock_settings.event_grid_topic = "integration-events"
            await publisher.publish_event(event)
        mock_client.send.assert_awaited_once()
