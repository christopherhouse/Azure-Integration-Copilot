"""Tests for artifact metadata endpoints."""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

_test_env = {
    "ENVIRONMENT": "test",
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "",
    "WEB_PUBSUB_ENDPOINT": "",
    "AZURE_CLIENT_ID": "",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from main import app  # noqa: E402

from domains.artifacts.models import Artifact, ArtifactStatus
from domains.tenants.models import Tenant, TenantStatus, Usage, User, UserRole, UserStatus


def _make_tenant(tenant_id: str = "t-001", display_name: str = "Test Tenant") -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id=tenant_id,
        partitionKey=tenant_id,
        displayName=display_name,
        ownerId="u-001",
        tierId="tier_free",
        status=TenantStatus.ACTIVE,
        usage=Usage(daily_analysis_reset_at=now),
        createdAt=now,
        updatedAt=now,
    )


def _make_user(tenant_id: str = "t-001", external_id: str = "dev-user-001") -> User:
    return User(
        id="u-001",
        partitionKey=tenant_id,
        tenantId=tenant_id,
        externalId=external_id,
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        createdAt=datetime.now(UTC),
    )


def _make_artifact(
    artifact_id: str = "art-001",
    tenant_id: str = "t-001",
    project_id: str = "prj-001",
    name: str = "test-file.json",
    status: ArtifactStatus = ArtifactStatus.UPLOADED,
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
        contentHash="sha256:abc123",
        createdAt=now,
        updatedAt=now,
    )


def _setup_context_mocks(tenant, user=None):
    """Return context manager patches for tenant context middleware."""
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
# GET /api/v1/projects/{projectId}/artifacts — List artifacts
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_artifacts_returns_paginated(client):
    """GET /api/v1/projects/{id}/artifacts returns paginated artifact list."""
    tenant = _make_tenant()
    artifacts = [_make_artifact(f"art-{i}", name=f"file-{i}.json") for i in range(2)]

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.list_artifacts = AsyncMock(return_value=(artifacts, 2))

            response = await client.get("/api/v1/projects/prj-001/artifacts")
            assert response.status_code == 200
            body = response.json()
            assert len(body["data"]) == 2
            assert body["pagination"]["total_count"] == 2
            assert "meta" in body


@pytest.mark.asyncio
async def test_list_artifacts_empty(client):
    """GET /api/v1/projects/{id}/artifacts returns empty list."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.list_artifacts = AsyncMock(return_value=([], 0))

            response = await client.get("/api/v1/projects/prj-001/artifacts")
            assert response.status_code == 200
            body = response.json()
            assert body["data"] == []
            assert body["pagination"]["total_count"] == 0


@pytest.mark.asyncio
async def test_list_artifacts_with_status_filter(client):
    """GET /api/v1/projects/{id}/artifacts?status=uploaded filters by status."""
    tenant = _make_tenant()
    artifacts = [_make_artifact(status=ArtifactStatus.UPLOADED)]

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.list_artifacts = AsyncMock(return_value=(artifacts, 1))

            response = await client.get("/api/v1/projects/prj-001/artifacts?status=uploaded")
            assert response.status_code == 200
            body = response.json()
            assert len(body["data"]) == 1
            # Verify the service was called with the status filter
            mock_svc.list_artifacts.assert_called_once()
            call_args = mock_svc.list_artifacts.call_args
            assert call_args[0][4] == ArtifactStatus.UPLOADED or call_args[1].get("status_filter") == ArtifactStatus.UPLOADED


@pytest.mark.asyncio
async def test_list_artifacts_pagination(client):
    """GET /api/v1/projects/{id}/artifacts supports pagination."""
    tenant = _make_tenant()
    artifacts = [_make_artifact()]

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.list_artifacts = AsyncMock(return_value=(artifacts, 10))

            response = await client.get("/api/v1/projects/prj-001/artifacts?page=2&pageSize=5")
            assert response.status_code == 200
            body = response.json()
            assert body["pagination"]["page"] == 2
            assert body["pagination"]["page_size"] == 5
            assert body["pagination"]["total_count"] == 10
            assert body["pagination"]["total_pages"] == 2


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{projectId}/artifacts/{artifactId} — Get artifact
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_artifact_returns_artifact(client):
    """GET /api/v1/projects/{id}/artifacts/{id} returns artifact metadata."""
    tenant = _make_tenant()
    artifact = _make_artifact()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.get_artifact = AsyncMock(return_value=artifact)

            response = await client.get("/api/v1/projects/prj-001/artifacts/art-001")
            assert response.status_code == 200
            body = response.json()
            assert body["data"]["id"] == "art-001"
            assert body["data"]["name"] == "test-file.json"
            assert body["data"]["artifactType"] == "logic_app_workflow"
            assert body["data"]["status"] == "uploaded"
            assert body["data"]["fileSizeBytes"] == 1024


@pytest.mark.asyncio
async def test_get_artifact_returns_404_when_not_found(client):
    """GET /api/v1/projects/{id}/artifacts/{id} returns 404 for missing artifact."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.get_artifact = AsyncMock(return_value=None)

            response = await client.get("/api/v1/projects/prj-001/artifacts/art-nonexistent")
            assert response.status_code == 404
            body = response.json()
            assert body["error"]["code"] == "RESOURCE_NOT_FOUND"


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{projectId}/artifacts/{artifactId} — Soft-delete
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_artifact_returns_204(client):
    """DELETE /api/v1/projects/{id}/artifacts/{id} soft-deletes and returns 204."""
    tenant = _make_tenant()
    artifact = _make_artifact()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.delete_artifact = AsyncMock(return_value=artifact)

            response = await client.delete("/api/v1/projects/prj-001/artifacts/art-001")
            assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_artifact_returns_404_when_not_found(client):
    """DELETE /api/v1/projects/{id}/artifacts/{id} returns 404 for missing artifact."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.delete_artifact = AsyncMock(return_value=None)

            response = await client.delete("/api/v1/projects/prj-001/artifacts/art-nonexistent")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def test_artifact_routes_registered():
    """Artifact routes are registered in the app."""
    routes = [route.path for route in app.routes if hasattr(route, "path")]
    assert "/api/v1/projects/{project_id}/artifacts" in routes
    assert "/api/v1/projects/{project_id}/artifacts/{artifact_id}" in routes
