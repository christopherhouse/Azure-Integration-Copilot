"""Tests for CloudEvents builder and Event Grid publisher."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

_test_env = {
    "ENVIRONMENT": "test",
    "COSMOS_DB_ENDPOINT": "",
    "BLOB_STORAGE_ENDPOINT": "",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "",
    "WEB_PUBSUB_ENDPOINT": "",
    "AZURE_CLIENT_ID": "",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from shared.event_types import (
        EVENT_ARTIFACT_UPLOADED,
        EVENT_SOURCE,
        ArtifactUploadedData,
    )
    from shared.events import EventGridPublisher, build_cloud_event


# ---------------------------------------------------------------------------
# build_cloud_event
# ---------------------------------------------------------------------------


class TestBuildCloudEvent:
    """Tests for the build_cloud_event helper."""

    def test_creates_cloud_event_with_required_fields(self):
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            source=EVENT_SOURCE,
            subject="tenants/t-1/projects/p-1/artifacts/a-1",
            data={"tenantId": "t-1"},
        )

        assert event.type == EVENT_ARTIFACT_UPLOADED
        assert event.source == EVENT_SOURCE
        assert event.subject == "tenants/t-1/projects/p-1/artifacts/a-1"
        assert event.data == {"tenantId": "t-1"}
        assert event.specversion == "1.0"
        assert event.datacontenttype == "application/json"

    def test_generates_unique_event_id(self):
        event1 = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            source=EVENT_SOURCE,
            subject="tenants/t-1/projects/p-1/artifacts/a-1",
            data={},
        )
        event2 = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            source=EVENT_SOURCE,
            subject="tenants/t-1/projects/p-1/artifacts/a-1",
            data={},
        )

        assert event1.id != event2.id

    def test_event_id_has_evt_prefix(self):
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            source=EVENT_SOURCE,
            subject="tenants/t-1/projects/p-1/artifacts/a-1",
            data={},
        )

        assert event.id.startswith("evt_")

    def test_event_time_is_set(self):
        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            source=EVENT_SOURCE,
            subject="tenants/t-1/projects/p-1/artifacts/a-1",
            data={},
        )

        assert event.time is not None


# ---------------------------------------------------------------------------
# ArtifactUploadedData
# ---------------------------------------------------------------------------


class TestArtifactUploadedData:
    """Tests for the ArtifactUploadedData model."""

    def test_serializes_to_camel_case(self):
        data = ArtifactUploadedData(
            tenantId="t-1",
            projectId="p-1",
            artifactId="a-1",
            artifactType="logic_app_workflow",
            blobPath="tenants/t-1/projects/p-1/artifacts/a-1/workflow.json",
            fileSizeBytes=1024,
            contentHash="sha256:abc123",
        )
        dumped = data.model_dump(by_alias=True)

        assert dumped["tenantId"] == "t-1"
        assert dumped["projectId"] == "p-1"
        assert dumped["artifactId"] == "a-1"
        assert dumped["artifactType"] == "logic_app_workflow"
        assert dumped["blobPath"] == "tenants/t-1/projects/p-1/artifacts/a-1/workflow.json"
        assert dumped["fileSizeBytes"] == 1024
        assert dumped["contentHash"] == "sha256:abc123"

    def test_accepts_python_names(self):
        data = ArtifactUploadedData(
            tenant_id="t-1",
            project_id="p-1",
            artifact_id="a-1",
            artifact_type="logic_app_workflow",
            blob_path="path/to/blob",
            file_size_bytes=512,
            content_hash="sha256:def456",
        )

        assert data.tenant_id == "t-1"
        assert data.blob_path == "path/to/blob"


# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------


class TestEventTypeConstants:
    """Tests for event type constant values."""

    def test_artifact_uploaded_type(self):
        assert EVENT_ARTIFACT_UPLOADED == "com.integration-copilot.artifact.uploaded.v1"

    def test_event_source(self):
        assert EVENT_SOURCE == "/integration-copilot/api"


# ---------------------------------------------------------------------------
# EventGridPublisher.publish
# ---------------------------------------------------------------------------


class TestEventGridPublisherPublish:
    """Tests for EventGridPublisher.publish()."""

    @pytest.mark.asyncio
    async def test_publish_sends_event_via_client(self):
        """publish() calls client.send() with the CloudEvent."""
        publisher = EventGridPublisher()
        mock_client = AsyncMock()
        publisher._client = mock_client
        publisher._credential = AsyncMock()

        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            source=EVENT_SOURCE,
            subject="tenants/t-1/projects/p-1/artifacts/a-1",
            data={"tenantId": "t-1"},
        )

        with patch("shared.events.settings") as mock_settings:
            mock_settings.event_grid_namespace_endpoint = "https://eg.eastus.eventgrid.azure.net"
            mock_settings.event_grid_topic = "integration-events"
            await publisher.publish(event)

        mock_client.send.assert_awaited_once_with(event)

    @pytest.mark.asyncio
    async def test_publish_skips_when_endpoint_not_configured(self):
        """publish() is a no-op when the endpoint is empty."""
        publisher = EventGridPublisher()

        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            source=EVENT_SOURCE,
            subject="tenants/t-1/projects/p-1/artifacts/a-1",
            data={"tenantId": "t-1"},
        )

        with patch("shared.events.settings") as mock_settings:
            mock_settings.event_grid_namespace_endpoint = ""
            await publisher.publish(event)

        # No client should have been created
        assert publisher._client is None

    @pytest.mark.asyncio
    async def test_publish_creates_client_with_namespace_topic(self):
        """publish() initialises the client with namespace_topic from settings."""
        publisher = EventGridPublisher()

        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            source=EVENT_SOURCE,
            subject="tenants/t-1/projects/p-1/artifacts/a-1",
            data={"tenantId": "t-1"},
        )

        with (
            patch("shared.events.settings") as mock_settings,
            patch("shared.events.create_credential") as mock_cred,
            patch("shared.events.EventGridPublisherClient") as mock_cls,
        ):
            mock_settings.event_grid_namespace_endpoint = "https://eg.eastus.eventgrid.azure.net"
            mock_settings.event_grid_topic = "integration-events"
            mock_cred.return_value = AsyncMock()
            mock_instance = AsyncMock()
            mock_cls.return_value = mock_instance

            await publisher.publish(event)

            mock_cls.assert_called_once_with(
                endpoint="https://eg.eastus.eventgrid.azure.net",
                credential=mock_cred.return_value,
                namespace_topic="integration-events",
            )
            mock_instance.send.assert_awaited_once_with(event)


# ---------------------------------------------------------------------------
# Integration: build + publish ArtifactUploaded
# ---------------------------------------------------------------------------


class TestArtifactUploadedEventIntegration:
    """Integration tests combining build_cloud_event with ArtifactUploadedData."""

    def test_build_artifact_uploaded_event(self):
        """Build a complete ArtifactUploaded CloudEvent matching the spec."""
        data = ArtifactUploadedData(
            tenantId="tn_01",
            projectId="prj_01",
            artifactId="art_01",
            artifactType="logic_app_workflow",
            blobPath="tenants/tn_01/projects/prj_01/artifacts/art_01/workflow.json",
            fileSizeBytes=24576,
            contentHash="sha256:abc123",
        )

        event = build_cloud_event(
            event_type=EVENT_ARTIFACT_UPLOADED,
            source=EVENT_SOURCE,
            subject=f"tenants/{data.tenant_id}/projects/{data.project_id}/artifacts/{data.artifact_id}",
            data=data.model_dump(by_alias=True),
        )

        assert event.type == "com.integration-copilot.artifact.uploaded.v1"
        assert event.source == "/integration-copilot/api"
        assert event.subject == "tenants/tn_01/projects/prj_01/artifacts/art_01"
        assert event.data["tenantId"] == "tn_01"
        assert event.data["projectId"] == "prj_01"
        assert event.data["artifactId"] == "art_01"
        assert event.data["artifactType"] == "logic_app_workflow"
        assert event.data["blobPath"] == "tenants/tn_01/projects/prj_01/artifacts/art_01/workflow.json"
        assert event.data["fileSizeBytes"] == 24576
        assert event.data["contentHash"] == "sha256:abc123"
        assert event.specversion == "1.0"
