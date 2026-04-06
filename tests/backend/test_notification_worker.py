"""Tests for the notification worker handler (NotificationHandler)."""

import os
from unittest.mock import AsyncMock, patch

import pytest

_test_env = {
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "https://fake-eg.westus-1.eventgrid.azure.net",
    "WEB_PUBSUB_ENDPOINT": "https://fake-pubsub.webpubsub.azure.com",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from shared.event_types import (
        EVENT_ANALYSIS_COMPLETED,
        EVENT_ANALYSIS_FAILED,
        EVENT_ARTIFACT_PARSED,
        EVENT_ARTIFACT_SCAN_PASSED,
        EVENT_GRAPH_UPDATED,
    )
    from workers.notification.handler import NotificationHandler


def _make_pubsub():
    pubsub = AsyncMock()
    pubsub.send_to_group = AsyncMock()
    return pubsub


def _make_event_data(
    event_type: str = EVENT_GRAPH_UPDATED,
    tenant_id: str = "t1",
    project_id: str | None = "p1",
) -> dict:
    data = {
        "_event_type": event_type,
        "tenantId": tenant_id,
        "artifactId": "art_001",
    }
    if project_id:
        data["projectId"] = project_id
    return data


class TestNotificationHandlerIsAlreadyProcessed:
    """Notifications are idempotent — always returns False."""

    @pytest.mark.asyncio
    async def test_always_returns_false(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        result = await handler.is_already_processed({"anything": "value"})
        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_with_empty_data(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        result = await handler.is_already_processed({})
        assert result is False


class TestNotificationHandlerHandle:
    """Tests for the notification handler ``handle`` method."""

    @pytest.mark.asyncio
    async def test_sends_notification_for_mapped_event(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        event_data = _make_event_data(event_type=EVENT_GRAPH_UPDATED)

        await handler.handle(event_data)

        assert pubsub.send_to_group.await_count == 2  # tenant + project

    @pytest.mark.asyncio
    async def test_sends_to_tenant_group(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        event_data = _make_event_data(event_type=EVENT_GRAPH_UPDATED)

        await handler.handle(event_data)

        # First call should be to tenant group
        first_call = pubsub.send_to_group.call_args_list[0]
        assert first_call.kwargs["group"] == "tenant:t1"
        payload = first_call.kwargs["data"]
        assert payload["type"] == "graph.updated"

    @pytest.mark.asyncio
    async def test_sends_to_project_group_when_project_id_present(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        event_data = _make_event_data(event_type=EVENT_GRAPH_UPDATED)

        await handler.handle(event_data)

        # Second call should be to project group
        second_call = pubsub.send_to_group.call_args_list[1]
        assert second_call.kwargs["group"] == "project:t1:p1"

    @pytest.mark.asyncio
    async def test_sends_only_to_tenant_group_without_project_id(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        event_data = _make_event_data(
            event_type=EVENT_GRAPH_UPDATED, project_id=None
        )

        await handler.handle(event_data)

        # Only one send (tenant group only)
        assert pubsub.send_to_group.await_count == 1
        call = pubsub.send_to_group.call_args_list[0]
        assert call.kwargs["group"] == "tenant:t1"

    @pytest.mark.asyncio
    async def test_skips_unmapped_event_types(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        event_data = {
            "_event_type": "com.integration-copilot.unknown.event.v1",
            "tenantId": "t1",
        }

        await handler.handle(event_data)

        pubsub.send_to_group.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_when_no_event_type(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        event_data = {"tenantId": "t1"}

        await handler.handle(event_data)

        pubsub.send_to_group.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_skips_when_missing_tenant_id(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        event_data = {
            "_event_type": EVENT_GRAPH_UPDATED,
            # No tenantId
        }

        await handler.handle(event_data)

        pubsub.send_to_group.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_maps_analysis_completed_event(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        event_data = _make_event_data(event_type=EVENT_ANALYSIS_COMPLETED)

        await handler.handle(event_data)

        first_call = pubsub.send_to_group.call_args_list[0]
        payload = first_call.kwargs["data"]
        assert payload["type"] == "analysis.completed"

    @pytest.mark.asyncio
    async def test_maps_analysis_failed_event(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        event_data = _make_event_data(event_type=EVENT_ANALYSIS_FAILED)

        await handler.handle(event_data)

        first_call = pubsub.send_to_group.call_args_list[0]
        payload = first_call.kwargs["data"]
        assert payload["type"] == "analysis.failed"

    @pytest.mark.asyncio
    async def test_maps_artifact_scan_passed_event(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        event_data = _make_event_data(event_type=EVENT_ARTIFACT_SCAN_PASSED)

        await handler.handle(event_data)

        first_call = pubsub.send_to_group.call_args_list[0]
        payload = first_call.kwargs["data"]
        assert payload["type"] == "artifact.status_changed"

    @pytest.mark.asyncio
    async def test_maps_artifact_parsed_event(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)
        event_data = _make_event_data(event_type=EVENT_ARTIFACT_PARSED)

        await handler.handle(event_data)

        first_call = pubsub.send_to_group.call_args_list[0]
        payload = first_call.kwargs["data"]
        assert payload["type"] == "artifact.status_changed"


class TestNotificationHandlerBuildPayload:
    """Tests for the _build_payload static method."""

    def test_strips_internal_fields(self):
        event_data = {
            "_event_type": "some.event",
            "_internal": "secret",
            "tenantId": "t1",
            "projectId": "p1",
            "artifactId": "art_001",
            "partitionKey": "t1:p1",
        }
        payload = NotificationHandler._build_payload(event_data)

        assert "_event_type" not in payload
        assert "_internal" not in payload
        assert "partitionKey" not in payload
        assert payload["tenantId"] == "t1"
        assert payload["projectId"] == "p1"
        assert payload["artifactId"] == "art_001"

    def test_preserves_public_fields(self):
        event_data = {
            "tenantId": "t1",
            "analysisId": "ana_001",
            "verdict": "PASSED",
        }
        payload = NotificationHandler._build_payload(event_data)

        assert payload == event_data

    def test_returns_empty_dict_for_only_internal_fields(self):
        event_data = {
            "_event_type": "some.event",
            "partitionKey": "pk",
        }
        payload = NotificationHandler._build_payload(event_data)
        assert payload == {}


class TestNotificationHandlerHandleFailure:
    """Tests for the notification failure handler."""

    @pytest.mark.asyncio
    async def test_does_not_crash(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)

        # Should not raise
        await handler.handle_failure(
            {"_event_type": "some.event", "tenantId": "t1"},
            RuntimeError("pubsub down"),
        )

    @pytest.mark.asyncio
    async def test_does_not_crash_with_empty_data(self):
        pubsub = _make_pubsub()
        handler = NotificationHandler(pubsub_service=pubsub)

        # Should not raise even with empty data
        await handler.handle_failure({}, RuntimeError("fail"))
