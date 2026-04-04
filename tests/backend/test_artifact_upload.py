"""Tests for artifact upload endpoint."""

import io
import json
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

from domains.artifacts.service import ArtifactService
from domains.projects.models import Project, ProjectStatus
from domains.tenants.models import FREE_TIER, TierDefinition, TierFeatures, TierLimits
from shared.exceptions import NotFoundError, QuotaExceededError

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
    from main import app  # noqa: E402

from domains.artifacts.models import Artifact, ArtifactStatus
from domains.tenants.models import Tenant, TenantStatus, TierLimits, Usage, User, UserRole, UserStatus


def _make_tenant(tenant_id: str = "t-001") -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id=tenant_id,
        partitionKey=tenant_id,
        displayName="Test Tenant",
        ownerId="u-001",
        tierId="tier_free",
        status=TenantStatus.ACTIVE,
        usage=Usage(daily_analysis_reset_at=now),
        createdAt=now,
        updatedAt=now,
    )


def _make_user(tenant_id: str = "t-001") -> User:
    return User(
        id="u-001",
        partitionKey=tenant_id,
        tenantId=tenant_id,
        externalId="dev-user-001",
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        createdAt=datetime.now(UTC),
    )


def _make_artifact(
    artifact_id: str = "art_abc123",
    tenant_id: str = "t-001",
    project_id: str = "prj-001",
    name: str = "workflow.json",
    status: ArtifactStatus = ArtifactStatus.UPLOADED,
    blob_path: str | None = None,
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
        blobPath=blob_path or f"tenants/{tenant_id}/projects/{project_id}/artifacts/{artifact_id}/{name}",
        contentHash="sha256:abc123def456",
        createdAt=now,
        updatedAt=now,
    )


def _setup_context_mocks(tenant, user=None):
    if user is None:
        user = _make_user(tenant.id if tenant else "t-001")
    return (
        patch("middleware.tenant_context.user_service", **{
            "get_user_by_external_id": AsyncMock(return_value=user),
        }),
        patch("middleware.tenant_context.tenant_service", **{
            "get_tenant": AsyncMock(return_value=tenant),
        }),
        patch("middleware.tenant_context.settings", **{
            "skip_auth": True,
            "cosmos_db_endpoint": "https://fake.documents.azure.com/",
        }),
    )


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# POST /api/v1/projects/{projectId}/artifacts — Upload
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_artifact_returns_202(client):
    """POST upload returns 202 with artifact metadata."""
    tenant = _make_tenant()
    artifact = _make_artifact()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.upload_artifact = AsyncMock(return_value=artifact)

            response = await client.post(
                "/api/v1/projects/prj-001/artifacts",
                files={"file": ("workflow.json", b'{"definition": {"triggers": {}}}', "application/json")},
            )
            assert response.status_code == 202
            body = response.json()
            assert body["data"]["id"] == "art_abc123"
            assert body["data"]["name"] == "workflow.json"
            assert body["data"]["artifactType"] == "logic_app_workflow"
            assert body["data"]["status"] == "uploaded"
            assert "meta" in body


@pytest.mark.asyncio
async def test_upload_artifact_returns_413_for_large_file(client):
    """POST upload returns 413 when file exceeds size limit."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.upload_artifact = AsyncMock(
                side_effect=ValueError("File size 20971520 exceeds maximum 10485760 bytes (10 MB).")
            )

            response = await client.post(
                "/api/v1/projects/prj-001/artifacts",
                files={"file": ("big.json", b"x" * 100, "application/json")},
            )
            assert response.status_code == 413
            body = response.json()
            assert body["error"]["code"] == "FILE_TOO_LARGE"


@pytest.mark.asyncio
async def test_upload_artifact_with_type_override(client):
    """POST upload with artifact_type form field passes override to service."""
    tenant = _make_tenant()
    artifact = _make_artifact()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.upload_artifact = AsyncMock(return_value=artifact)

            response = await client.post(
                "/api/v1/projects/prj-001/artifacts",
                files={"file": ("workflow.json", b'{}', "application/json")},
                data={"artifact_type": "openapi_spec"},
            )
            assert response.status_code == 202
            # Verify the override was passed
            call_kwargs = mock_svc.upload_artifact.call_args
            assert call_kwargs.kwargs.get("artifact_type_override") == "openapi_spec"


@pytest.mark.asyncio
async def test_upload_artifact_returns_401_without_tenant(client):
    """POST upload without tenant context returns 401."""
    # Patch settings so the middleware takes the dev-mode-no-cosmos path,
    # which sets request.state.tenant = None and lets the route handler
    # return 401.
    with patch("middleware.tenant_context.settings", skip_auth=True, cosmos_db_endpoint=""):
        response = await client.post(
            "/api/v1/projects/prj-001/artifacts",
            files={"file": ("test.json", b'{}', "application/json")},
        )
        assert response.status_code == 401


@pytest.mark.asyncio
async def test_upload_unknown_type_sets_unsupported(client):
    """Upload of unknown file type returns artifact with unsupported status."""
    tenant = _make_tenant()
    artifact = _make_artifact(status=ArtifactStatus.UNSUPPORTED)
    artifact.artifact_type = "unknown"

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.upload_artifact = AsyncMock(return_value=artifact)

            response = await client.post(
                "/api/v1/projects/prj-001/artifacts",
                files={"file": ("readme.txt", b"Hello", "text/plain")},
            )
            assert response.status_code == 202
            body = response.json()
            assert body["data"]["status"] == "unsupported"
            assert body["data"]["artifactType"] == "unknown"


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def test_upload_and_download_routes_registered():
    """Upload and download routes are registered in the app."""
    routes = [route.path for route in app.routes if hasattr(route, "path")]
    assert "/api/v1/projects/{project_id}/artifacts" in routes
    assert "/api/v1/projects/{project_id}/artifacts/{artifact_id}/download" in routes


# ---------------------------------------------------------------------------
# Per-project artifact quota enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_artifact_returns_429_per_project_quota(client):
    """POST upload returns 429 when per-project artifact quota is exceeded."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.upload_artifact = AsyncMock(
                side_effect=QuotaExceededError(
                    message="Artifact limit per project exceeded.",
                    detail={
                        "limit": "max_artifacts_per_project",
                        "current": 25,
                        "max": 25,
                    },
                )
            )

            response = await client.post(
                "/api/v1/projects/prj-001/artifacts",
                files={"file": ("workflow.json", b'{"definition": {}}', "application/json")},
            )
            assert response.status_code == 429
            body = response.json()
            assert body["error"]["code"] == "QUOTA_EXCEEDED"


# ---------------------------------------------------------------------------
# ArtifactService unit tests — quota & counter logic
# ---------------------------------------------------------------------------


def _make_project(
    project_id: str = "prj-001",
    tenant_id: str = "t-001",
    artifact_count: int = 0,
) -> Project:
    return Project(
        id=project_id,
        partitionKey=tenant_id,
        tenantId=tenant_id,
        name="Test",
        createdBy="u-001",
        artifactCount=artifact_count,
    )


@pytest.mark.asyncio
async def test_upload_artifact_service_checks_project_quota():
    """ArtifactService.upload_artifact raises QuotaExceededError when project quota is reached."""
    tenant = _make_tenant()
    tier = TierDefinition(
        id="tier_free",
        name="Free",
        slug="free",
        limits=TierLimits(max_artifacts_per_project=25),
    )
    project = _make_project(artifact_count=25)

    file = MagicMock()
    file.read = AsyncMock(side_effect=[b"small content", b""])
    file.seek = AsyncMock()
    file.filename = "workflow.json"
    file.content_type = "application/json"

    with (
        patch("domains.artifacts.service.project_repository") as mock_proj_repo,
        patch("domains.artifacts.service.artifact_repository"),
        patch("domains.artifacts.service.tenant_repository"),
        patch("domains.artifacts.service.blob_service"),
        patch("domains.artifacts.service.event_grid_publisher"),
    ):
        mock_proj_repo.get_by_id = AsyncMock(return_value=project)

        svc = ArtifactService()
        with pytest.raises(QuotaExceededError) as exc_info:
            await svc.upload_artifact(
                tenant=tenant,
                tier=tier,
                project_id="prj-001",
                file=file,
            )

        assert exc_info.value.status_code == 429
        assert exc_info.value.detail["limit"] == "max_artifacts_per_project"
        assert exc_info.value.detail["current"] == 25
        assert exc_info.value.detail["max"] == 25


@pytest.mark.asyncio
async def test_upload_artifact_increments_project_artifact_count():
    """ArtifactService.upload_artifact increments project artifact_count on success."""
    tenant = _make_tenant()
    tier = FREE_TIER
    project = _make_project(artifact_count=5)
    artifact = _make_artifact()

    file = MagicMock()
    file.read = AsyncMock(side_effect=[b"small content", b""])
    file.seek = AsyncMock()
    file.filename = "workflow.json"
    file.content_type = "application/json"

    with (
        patch("domains.artifacts.service.project_repository") as mock_proj_repo,
        patch("domains.artifacts.service.artifact_repository") as mock_art_repo,
        patch("domains.artifacts.service.tenant_repository") as mock_tenant_repo,
        patch("domains.artifacts.service.blob_service") as mock_blob,
        patch("domains.artifacts.service.event_grid_publisher") as mock_events,
        patch("domains.artifacts.service.detect_artifact_type", new_callable=AsyncMock, return_value="logic_app_workflow"),
        patch("domains.artifacts.service.compute_hash", new_callable=AsyncMock, return_value="sha256:abc123"),
    ):
        mock_proj_repo.get_by_id = AsyncMock(return_value=project)
        mock_proj_repo.increment_artifact_count = AsyncMock()
        uploading_artifact = _make_artifact(status=ArtifactStatus.UPLOADING)
        mock_art_repo.create = AsyncMock(return_value=uploading_artifact)
        mock_art_repo.update = AsyncMock(return_value=artifact)
        mock_blob.upload_blob = AsyncMock()
        mock_tenant_repo.increment_usage = AsyncMock()
        mock_events.publish_event = AsyncMock()

        svc = ArtifactService()
        result = await svc.upload_artifact(
            tenant=tenant,
            tier=tier,
            project_id="prj-001",
            file=file,
        )

        assert result is not None
        mock_proj_repo.increment_artifact_count.assert_called_once_with(
            tenant.id, "prj-001"
        )
        mock_tenant_repo.increment_usage.assert_called_once_with(
            tenant.id, "total_artifact_count"
        )


@pytest.mark.asyncio
async def test_delete_artifact_decrements_counters():
    """ArtifactService.delete_artifact decrements both tenant and project counters."""
    artifact = _make_artifact()

    with (
        patch("domains.artifacts.service.artifact_repository") as mock_art_repo,
        patch("domains.artifacts.service.tenant_repository") as mock_tenant_repo,
        patch("domains.artifacts.service.project_repository") as mock_proj_repo,
        patch("domains.artifacts.service.blob_service") as mock_blob,
        patch("domains.artifacts.service.graph_repository") as mock_graph,
    ):
        mock_art_repo.get_by_id = AsyncMock(return_value=artifact)
        mock_art_repo.soft_delete = AsyncMock(return_value=artifact)
        mock_tenant_repo.increment_usage = AsyncMock()
        mock_proj_repo.increment_artifact_count = AsyncMock()
        mock_blob.delete_blob = AsyncMock()
        mock_graph.delete_by_artifact_id = AsyncMock(return_value=0)

        svc = ArtifactService()
        result = await svc.delete_artifact("t-001", "prj-001", "art_abc123")

        assert result is not None
        mock_tenant_repo.increment_usage.assert_called_once_with(
            "t-001", "total_artifact_count", amount=-1
        )
        mock_proj_repo.increment_artifact_count.assert_called_once_with(
            "t-001", "prj-001", amount=-1
        )


# ---------------------------------------------------------------------------
# Block artifact uploads for non-existent projects (M1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_upload_artifact_rejects_nonexistent_project():
    """ArtifactService.upload_artifact raises NotFoundError when project does not exist."""
    tenant = _make_tenant()
    tier = TierDefinition(
        id="tier_free",
        name="Free",
        slug="free",
        limits=TierLimits(max_artifacts_per_project=25),
    )

    file = MagicMock()
    file.read = AsyncMock(side_effect=[b"small content", b""])
    file.seek = AsyncMock()
    file.filename = "workflow.json"
    file.content_type = "application/json"

    with (
        patch("domains.artifacts.service.project_repository") as mock_proj_repo,
        patch("domains.artifacts.service.artifact_repository"),
        patch("domains.artifacts.service.tenant_repository"),
        patch("domains.artifacts.service.blob_service"),
        patch("domains.artifacts.service.event_grid_publisher"),
    ):
        mock_proj_repo.get_by_id = AsyncMock(return_value=None)

        svc = ArtifactService()
        with pytest.raises(NotFoundError) as exc_info:
            await svc.upload_artifact(
                tenant=tenant,
                tier=tier,
                project_id="prj-nonexistent",
                file=file,
            )

        assert exc_info.value.status_code == 404
        assert exc_info.value.detail["project_id"] == "prj-nonexistent"
