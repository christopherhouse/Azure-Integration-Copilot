"""Tests for artifact download endpoint."""

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
    "BLOB_STORAGE_ENDPOINT": "https://fake-blob.blob.core.windows.net/",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "",
    "WEB_PUBSUB_ENDPOINT": "",
    "AZURE_CLIENT_ID": "",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from main import app  # noqa: E402

from domains.tenants.models import Tenant, TenantStatus, Usage, User, UserRole, UserStatus


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
# GET /api/v1/projects/{projectId}/artifacts/{artifactId}/download
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_download_artifact_returns_content(client):
    """GET download returns the raw file content with Content-Disposition."""
    tenant = _make_tenant()
    file_content = b'{"definition": {"triggers": {}}}'

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.download_artifact = AsyncMock(return_value=(file_content, "workflow.json"))

            response = await client.get("/api/v1/projects/prj-001/artifacts/art-001/download")
            assert response.status_code == 200
            assert response.content == file_content
            assert 'attachment; filename="workflow.json"' in response.headers["content-disposition"]


@pytest.mark.asyncio
async def test_download_artifact_returns_404_when_not_found(client):
    """GET download returns 404 for missing artifact."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.artifacts.router.artifact_service") as mock_svc:
            mock_svc.download_artifact = AsyncMock(return_value=None)

            response = await client.get("/api/v1/projects/prj-001/artifacts/art-nonexistent/download")
            assert response.status_code == 404
            body = response.json()
            assert body["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_download_artifact_returns_401_without_tenant(client):
    """GET download without tenant context returns 401."""
    # Patch settings so the middleware takes the dev-mode-no-cosmos path,
    # which sets request.state.tenant = None and lets the route handler
    # return 401.
    with patch("middleware.tenant_context.settings", skip_auth=True, cosmos_db_endpoint=""):
        response = await client.get("/api/v1/projects/prj-001/artifacts/art-001/download")
        assert response.status_code == 401
