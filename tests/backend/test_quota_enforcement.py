"""Tests for quota enforcement middleware — verifies 429 responses for quota violations."""

import os
import re
import sys
from datetime import UTC, datetime, timedelta
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

from domains.tenants.models import FREE_TIER, QuotaResult, Tenant, TenantStatus, Usage, User, UserRole, UserStatus


def _make_tenant(
    project_count: int = 0,
    total_artifact_count: int = 0,
    daily_analysis_count: int = 0,
) -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id="t-001",
        partitionKey="t-001",
        displayName="Test Tenant",
        ownerId="u-001",
        tierId="tier_free",
        status=TenantStatus.ACTIVE,
        usage=Usage(
            project_count=project_count,
            total_artifact_count=total_artifact_count,
            daily_analysis_count=daily_analysis_count,
            daily_analysis_reset_at=now + timedelta(days=1),
        ),
        createdAt=now,
        updatedAt=now,
    )


def _make_user() -> User:
    return User(
        id="u-001",
        partitionKey="t-001",
        tenantId="t-001",
        externalId="dev-user-001",
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        createdAt=datetime.now(UTC),
    )


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _setup_tenant_mocks(tenant):
    """Return context manager patches for tenant context middleware."""
    user = _make_user()
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


@pytest.mark.asyncio
async def test_quota_exceeded_max_projects(client):
    """POST /api/v1/projects returns 429 when project count equals max."""
    tenant = _make_tenant(project_count=3)  # FREE_TIER max_projects = 3

    mock1, mock2, mock3 = _setup_tenant_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("middleware.quota.quota_service") as mock_quota:
            mock_quota.check = AsyncMock(return_value=QuotaResult(
                allowed=False,
                limitName="max_projects",
                current=3,
                maximum=3,
            ))
            response = await client.post("/api/v1/projects", json={})
            assert response.status_code == 429
            body = response.json()
            assert body["error"]["code"] == "QUOTA_EXCEEDED"
            assert body["error"]["detail"]["limit"] == "max_projects"
            assert body["error"]["detail"]["current"] == 3
            assert body["error"]["detail"]["max"] == 3


@pytest.mark.asyncio
async def test_quota_exceeded_max_artifacts(client):
    """POST /api/v1/projects/{id}/artifacts returns 429 when artifact quota exceeded."""
    tenant = _make_tenant(total_artifact_count=50)  # FREE_TIER max_total_artifacts = 50

    mock1, mock2, mock3 = _setup_tenant_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("middleware.quota.quota_service") as mock_quota:
            mock_quota.check = AsyncMock(return_value=QuotaResult(
                allowed=False,
                limitName="max_total_artifacts",
                current=50,
                maximum=50,
            ))
            response = await client.post("/api/v1/projects/proj-123/artifacts", json={})
            # Gets 429 from quota middleware before reaching (non-existent) handler
            assert response.status_code == 429
            body = response.json()
            assert body["error"]["code"] == "QUOTA_EXCEEDED"
            assert body["error"]["detail"]["limit"] == "max_total_artifacts"


@pytest.mark.asyncio
async def test_quota_exceeded_daily_analyses(client):
    """POST /api/v1/projects/{id}/analyses returns 429 when daily analysis quota exceeded."""
    tenant = _make_tenant(daily_analysis_count=20)  # FREE_TIER max_daily_analyses = 20

    mock1, mock2, mock3 = _setup_tenant_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("middleware.quota.quota_service") as mock_quota:
            mock_quota.check = AsyncMock(return_value=QuotaResult(
                allowed=False,
                limitName="max_daily_analyses",
                current=20,
                maximum=20,
            ))
            response = await client.post("/api/v1/projects/proj-123/analyses", json={})
            assert response.status_code == 429
            body = response.json()
            assert body["error"]["code"] == "QUOTA_EXCEEDED"
            assert body["error"]["detail"]["limit"] == "max_daily_analyses"


@pytest.mark.asyncio
async def test_quota_allows_within_limit(client):
    """POST /api/v1/projects passes through when under quota."""
    tenant = _make_tenant(project_count=1)  # Under the limit

    mock1, mock2, mock3 = _setup_tenant_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("middleware.quota.quota_service") as mock_quota:
            mock_quota.check = AsyncMock(return_value=QuotaResult(
                allowed=True,
                limitName="max_projects",
                current=1,
                maximum=3,
            ))
            response = await client.post("/api/v1/projects", json={})
            # Should NOT return 429; route doesn't exist so we get 404
            assert response.status_code != 429


@pytest.mark.asyncio
async def test_quota_not_checked_for_get_requests(client):
    """GET requests are not subject to quota enforcement."""
    tenant = _make_tenant(project_count=3)

    mock1, mock2, mock3 = _setup_tenant_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.list_projects = AsyncMock(return_value=([], 0))
            response = await client.get("/api/v1/projects")
            # Should not be 429
            assert response.status_code != 429


@pytest.mark.asyncio
async def test_quota_response_body_structure(client):
    """Verify the 429 response body structure matches the spec."""
    tenant = _make_tenant(project_count=3)

    mock1, mock2, mock3 = _setup_tenant_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("middleware.quota.quota_service") as mock_quota:
            mock_quota.check = AsyncMock(return_value=QuotaResult(
                allowed=False,
                limitName="max_projects",
                current=3,
                maximum=3,
            ))
            response = await client.post("/api/v1/projects", json={})
            assert response.status_code == 429
            body = response.json()

            # Verify structure
            assert "error" in body
            error = body["error"]
            assert "code" in error
            assert "message" in error
            assert "detail" in error
            assert "limit" in error["detail"]
            assert "current" in error["detail"]
            assert "max" in error["detail"]
