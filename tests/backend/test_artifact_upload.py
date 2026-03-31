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
