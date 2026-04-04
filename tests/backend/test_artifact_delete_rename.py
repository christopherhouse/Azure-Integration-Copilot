"""Tests for artifact delete (with cleanup) and rename service methods."""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

_test_env = {
    "ENVIRONMENT": "test",
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "",
    "WEB_PUBSUB_ENDPOINT": "",
    "AZURE_CLIENT_ID": "",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    pass  # ensure settings load

from domains.artifacts.models import Artifact, ArtifactStatus
from domains.artifacts.service import ArtifactService


def _make_artifact(
    artifact_id: str = "art-001",
    tenant_id: str = "t-001",
    project_id: str = "prj-001",
    name: str = "test-file.json",
    status: ArtifactStatus = ArtifactStatus.UPLOADED,
    blob_path: str | None = "tenants/t-001/projects/prj-001/artifacts/art-001/test-file.json",
) -> Artifact:
    now = datetime.now(UTC)
    return Artifact(
        id=artifact_id,
        partitionKey=tenant_id,
        tenantId=tenant_id,
        projectId=project_id,
        name=name,
        artifactType="logic_app_workflow",
        status=status,
        fileSizeBytes=1024,
        blobPath=blob_path,
        contentHash="sha256:abc123",
        createdAt=now,
        updatedAt=now,
    )


# ---------------------------------------------------------------------------
# delete_artifact — full cleanup
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_artifact_cleans_up_blob():
    """delete_artifact should delete the blob from storage."""
    artifact = _make_artifact()
    svc = ArtifactService()

    with (
        patch("domains.artifacts.service.artifact_repository") as mock_repo,
        patch("domains.artifacts.service.blob_service") as mock_blob,
        patch("domains.artifacts.service.graph_repository") as mock_graph,
        patch("domains.artifacts.service.tenant_repository") as mock_tenant,
        patch("domains.artifacts.service.project_repository") as mock_project,
    ):
        mock_repo.get_by_id = AsyncMock(return_value=artifact)
        mock_repo.soft_delete = AsyncMock(return_value=artifact)
        mock_blob.delete_blob = AsyncMock()
        mock_graph.delete_by_artifact_id = AsyncMock(return_value=0)
        mock_tenant.increment_usage = AsyncMock()
        mock_project.increment_artifact_count = AsyncMock()

        result = await svc.delete_artifact("t-001", "prj-001", "art-001")

        assert result is not None
        mock_blob.delete_blob.assert_called_once_with(artifact.blob_path)


@pytest.mark.asyncio
async def test_delete_artifact_cleans_up_graph_docs():
    """delete_artifact should delete graph documents linked to the artifact."""
    artifact = _make_artifact()
    svc = ArtifactService()

    with (
        patch("domains.artifacts.service.artifact_repository") as mock_repo,
        patch("domains.artifacts.service.blob_service") as mock_blob,
        patch("domains.artifacts.service.graph_repository") as mock_graph,
        patch("domains.artifacts.service.tenant_repository") as mock_tenant,
        patch("domains.artifacts.service.project_repository") as mock_project,
    ):
        mock_repo.get_by_id = AsyncMock(return_value=artifact)
        mock_repo.soft_delete = AsyncMock(return_value=artifact)
        mock_blob.delete_blob = AsyncMock()
        mock_graph.delete_by_artifact_id = AsyncMock(return_value=3)
        mock_tenant.increment_usage = AsyncMock()
        mock_project.increment_artifact_count = AsyncMock()

        result = await svc.delete_artifact("t-001", "prj-001", "art-001")

        assert result is not None
        mock_graph.delete_by_artifact_id.assert_called_once_with(
            "t-001:prj-001", "art-001"
        )


@pytest.mark.asyncio
async def test_delete_artifact_without_blob_path():
    """delete_artifact should skip blob deletion when blob_path is None."""
    artifact = _make_artifact(blob_path=None)
    svc = ArtifactService()

    with (
        patch("domains.artifacts.service.artifact_repository") as mock_repo,
        patch("domains.artifacts.service.blob_service") as mock_blob,
        patch("domains.artifacts.service.graph_repository") as mock_graph,
        patch("domains.artifacts.service.tenant_repository") as mock_tenant,
        patch("domains.artifacts.service.project_repository") as mock_project,
    ):
        mock_repo.get_by_id = AsyncMock(return_value=artifact)
        mock_repo.soft_delete = AsyncMock(return_value=artifact)
        mock_blob.delete_blob = AsyncMock()
        mock_graph.delete_by_artifact_id = AsyncMock(return_value=0)
        mock_tenant.increment_usage = AsyncMock()
        mock_project.increment_artifact_count = AsyncMock()

        result = await svc.delete_artifact("t-001", "prj-001", "art-001")

        assert result is not None
        mock_blob.delete_blob.assert_not_called()


@pytest.mark.asyncio
async def test_delete_artifact_returns_none_for_missing():
    """delete_artifact should return None when artifact doesn't exist."""
    svc = ArtifactService()

    with (
        patch("domains.artifacts.service.artifact_repository") as mock_repo,
        patch("domains.artifacts.service.blob_service") as mock_blob,
        patch("domains.artifacts.service.graph_repository") as mock_graph,
    ):
        mock_repo.get_by_id = AsyncMock(return_value=None)
        mock_blob.delete_blob = AsyncMock()
        mock_graph.delete_by_artifact_id = AsyncMock()

        result = await svc.delete_artifact("t-001", "prj-001", "art-001")

        assert result is None
        mock_blob.delete_blob.assert_not_called()
        mock_graph.delete_by_artifact_id.assert_not_called()


# ---------------------------------------------------------------------------
# rename_artifact
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_rename_artifact_updates_name():
    """rename_artifact should update the artifact name and return it."""
    artifact = _make_artifact()
    renamed = _make_artifact(name="new-label.json")
    svc = ArtifactService()

    with (
        patch("domains.artifacts.service.artifact_repository") as mock_repo,
    ):
        mock_repo.get_by_id = AsyncMock(return_value=artifact)
        mock_repo.update = AsyncMock(return_value=renamed)

        result = await svc.rename_artifact("t-001", "prj-001", "art-001", "new-label.json")

        assert result is not None
        assert result.name == "new-label.json"
        mock_repo.update.assert_called_once()
        # Verify the name was updated before save
        saved_artifact = mock_repo.update.call_args[0][0]
        assert saved_artifact.name == "new-label.json"


@pytest.mark.asyncio
async def test_rename_artifact_returns_none_for_missing():
    """rename_artifact should return None when artifact doesn't exist."""
    svc = ArtifactService()

    with (
        patch("domains.artifacts.service.artifact_repository") as mock_repo,
    ):
        mock_repo.get_by_id = AsyncMock(return_value=None)

        result = await svc.rename_artifact("t-001", "prj-001", "art-missing", "new-name")

        assert result is None
        mock_repo.update.assert_not_called()
