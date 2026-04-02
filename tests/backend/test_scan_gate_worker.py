"""Tests for the scan-gate worker handler."""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

_test_env = {
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "https://fake-eg.westus-1.eventgrid.azure.net",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from domains.artifacts.models import Artifact, ArtifactStatus
    from workers.base import PermanentError, TransientError
    from workers.scan_gate.handler import ScanGateHandler


def _make_artifact(
    artifact_id: str = "art_test123",
    tenant_id: str = "t1",
    project_id: str = "p1",
    status: ArtifactStatus = ArtifactStatus.UPLOADED,
) -> Artifact:
    now = datetime.now(UTC)
    return Artifact(
        id=artifact_id,
        partitionKey=tenant_id,
        tenantId=tenant_id,
        projectId=project_id,
        name="test.json",
        artifactType="openapi",
        status=status,
        fileSizeBytes=1024,
        createdAt=now,
        updatedAt=now,
    )


def _make_event_data(
    tenant_id: str = "t1",
    project_id: str = "p1",
    artifact_id: str = "art_test123",
) -> dict:
    return {
        "tenantId": tenant_id,
        "projectId": project_id,
        "artifactId": artifact_id,
        "artifactType": "openapi",
        "blobPath": f"tenants/{tenant_id}/projects/{project_id}/artifacts/{artifact_id}/test.json",
        "fileSizeBytes": 1024,
        "contentHash": "abc123",
    }


class TestScanGateIsAlreadyProcessed:
    """Tests for the idempotency check."""

    @pytest.mark.asyncio
    async def test_returns_false_when_artifact_not_found(self):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=None)
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)
        result = await handler.is_already_processed(_make_event_data())

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_false_when_status_is_uploaded(self):
        artifact = _make_artifact(status=ArtifactStatus.UPLOADED)
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=artifact)
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)
        result = await handler.is_already_processed(_make_event_data())

        assert result is False

    @pytest.mark.asyncio
    async def test_returns_true_when_status_is_scan_passed(self):
        artifact = _make_artifact(status=ArtifactStatus.SCAN_PASSED)
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=artifact)
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)
        result = await handler.is_already_processed(_make_event_data())

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_status_is_parsed(self):
        artifact = _make_artifact(status=ArtifactStatus.PARSED)
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=artifact)
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)
        result = await handler.is_already_processed(_make_event_data())

        assert result is True

    @pytest.mark.asyncio
    async def test_returns_true_when_status_is_scan_failed(self):
        artifact = _make_artifact(status=ArtifactStatus.SCAN_FAILED)
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=artifact)
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)
        result = await handler.is_already_processed(_make_event_data())

        assert result is True


class TestScanGateHandle:
    """Tests for the scan-gate handler ``handle`` method."""

    @pytest.mark.asyncio
    async def test_transitions_to_scan_passed_and_publishes_event(self):
        artifact_uploaded = _make_artifact(status=ArtifactStatus.UPLOADED)
        artifact_scanning = _make_artifact(status=ArtifactStatus.SCANNING)
        artifact_passed = _make_artifact(status=ArtifactStatus.SCAN_PASSED)

        repo = AsyncMock()
        repo.update_status = AsyncMock(side_effect=[artifact_scanning, artifact_passed])
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)
        await handler.handle(_make_event_data())

        # Verify two status transitions: uploaded→scanning, scanning→scan_passed
        assert repo.update_status.await_count == 2
        calls = repo.update_status.await_args_list
        assert calls[0].args == ("t1", "art_test123", ArtifactStatus.SCANNING)
        assert calls[1].args == ("t1", "art_test123", ArtifactStatus.SCAN_PASSED)

        # Verify event published
        publisher.publish_event.assert_awaited_once()
        published_event = publisher.publish_event.call_args.args[0]
        assert published_event.type == "com.integration-copilot.artifact.scan-passed.v1"

    @pytest.mark.asyncio
    async def test_raises_permanent_error_when_artifact_not_found(self):
        repo = AsyncMock()
        repo.update_status = AsyncMock(return_value=None)
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)

        with pytest.raises(PermanentError, match="not found"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_first_transition_failure(self):
        repo = AsyncMock()
        repo.update_status = AsyncMock(side_effect=RuntimeError("cosmos timeout"))
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)

        with pytest.raises(TransientError, match="scanning"):
            await handler.handle(_make_event_data())

    @pytest.mark.asyncio
    async def test_raises_transient_error_on_second_transition_failure(self):
        artifact_scanning = _make_artifact(status=ArtifactStatus.SCANNING)
        repo = AsyncMock()
        repo.update_status = AsyncMock(
            side_effect=[artifact_scanning, RuntimeError("cosmos timeout")]
        )
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)

        with pytest.raises(TransientError, match="scan_passed"):
            await handler.handle(_make_event_data())


class TestScanGateHandleFailure:
    """Tests for the scan-gate failure handler."""

    @pytest.mark.asyncio
    async def test_transitions_to_scan_failed(self):
        artifact = _make_artifact(status=ArtifactStatus.SCANNING)
        artifact_failed = _make_artifact(status=ArtifactStatus.SCAN_FAILED)

        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=artifact)
        repo.update_status = AsyncMock(return_value=artifact_failed)
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)
        await handler.handle_failure(_make_event_data(), PermanentError("bad data"))

        repo.update_status.assert_awaited_once_with("t1", "art_test123", ArtifactStatus.SCAN_FAILED)

        # Verify failure event published
        publisher.publish_event.assert_awaited_once()
        published_event = publisher.publish_event.call_args.args[0]
        assert published_event.type == "com.integration-copilot.artifact.scan-failed.v1"

    @pytest.mark.asyncio
    async def test_skips_transition_if_already_past_scan(self):
        artifact = _make_artifact(status=ArtifactStatus.SCAN_PASSED)

        repo = AsyncMock()
        repo.get_by_id = AsyncMock(return_value=artifact)
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)
        await handler.handle_failure(_make_event_data(), PermanentError("bad data"))

        repo.update_status.assert_not_awaited()

    @pytest.mark.asyncio
    async def test_does_not_raise_on_internal_error(self):
        repo = AsyncMock()
        repo.get_by_id = AsyncMock(side_effect=RuntimeError("db down"))
        publisher = AsyncMock()

        handler = ScanGateHandler(artifact_repository=repo, event_publisher=publisher)
        # Should not raise
        await handler.handle_failure(_make_event_data(), PermanentError("bad data"))
