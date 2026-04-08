"""Tests for analysis API endpoints."""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

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
    from main import app
    from domains.analysis.models import Analysis, AnalysisResult, AnalysisStatus
    from domains.analysis.router import analysis_service
    from domains.tenants.models import QuotaResult, Tenant, TenantStatus, Usage, User, UserRole, UserStatus


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
        patch("middleware.quota.quota_service", **{
            "check": AsyncMock(return_value=QuotaResult(
                allowed=True,
                limitName="max_daily_analyses",
                current=0,
                maximum=10,
            )),
        }),
    )


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


def _make_analysis(
    analysis_id: str = "ana_test123",
    tenant_id: str = "t-001",
    project_id: str = "p1",
    status: AnalysisStatus = AnalysisStatus.PENDING,
) -> Analysis:
    now = datetime.now(UTC)
    return Analysis(
        id=analysis_id,
        partitionKey=f"{tenant_id}:{project_id}",
        tenantId=tenant_id,
        projectId=project_id,
        prompt="What are the main integration patterns?",
        status=status,
        requestedBy="u-001",
        createdAt=now,
    )


class TestCreateAnalysisEndpoint:
    """Tests for POST /api/v1/projects/{projectId}/analyses."""

    @pytest.mark.asyncio
    async def test_returns_202_on_success(self, client):
        tenant = _make_tenant()
        analysis = _make_analysis()
        mock1, mock2, mock3, mock4 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3, mock4:
            with patch.object(
                analysis_service,
                "create_analysis",
                new_callable=AsyncMock,
                return_value=analysis,
            ):
                resp = await client.post(
                    "/api/v1/projects/p1/analyses",
                    json={"prompt": "What are the main integration patterns?"},
                )

        assert resp.status_code == 202
        body = resp.json()
        assert body["data"]["id"] == "ana_test123"
        assert body["data"]["status"] == "pending"
        assert body["data"]["prompt"] == "What are the main integration patterns?"

    @pytest.mark.asyncio
    async def test_increments_daily_analysis_count(self, client):
        """Verify that creating an analysis increments the daily_analysis_count."""
        tenant = _make_tenant()
        analysis = _make_analysis()
        mock1, mock2, mock3, mock4 = _setup_context_mocks(tenant)

        with mock1, mock2, mock3, mock4:
            with patch("domains.analysis.service.tenant_repository") as mock_tenant_repo:
                mock_tenant_repo.increment_usage = AsyncMock()
                with patch("domains.analysis.service.build_cloud_event") as mock_build_event:
                    mock_build_event.return_value = None  # We don't care about the event object
                    with patch.object(
                        analysis_service._repo,
                        "create",
                        new_callable=AsyncMock,
                    ):
                        with patch.object(
                            analysis_service._publisher,
                            "publish_event",
                            new_callable=AsyncMock,
                        ):
                            resp = await client.post(
                                "/api/v1/projects/p1/analyses",
                                json={"prompt": "test"},
                            )

        assert resp.status_code == 202
        mock_tenant_repo.increment_usage.assert_called_once_with("t-001", "daily_analysis_count")

    @pytest.mark.asyncio
    async def test_returns_401_when_no_tenant_context(self, client):
        """When auth is skipped and cosmos_db_endpoint is empty, tenant is None → 401."""
        resp = await client.post(
            "/api/v1/projects/p1/analyses",
            json={"prompt": "test"},
        )
        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_passes_user_id_to_service(self, client):
        tenant = _make_tenant()
        analysis = _make_analysis()
        mock1, mock2, mock3, mock4 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3, mock4:
            with patch.object(
                analysis_service,
                "create_analysis",
                new_callable=AsyncMock,
                return_value=analysis,
            ) as mock_create:
                await client.post(
                    "/api/v1/projects/p1/analyses",
                    json={"prompt": "Analyze this"},
                )

        # Verify service was called with correct arguments
        mock_create.assert_awaited_once()
        call_kwargs = mock_create.call_args.kwargs
        assert call_kwargs["tenant_id"] == "t-001"
        assert call_kwargs["project_id"] == "p1"
        assert call_kwargs["prompt"] == "Analyze this"


class TestListAnalysesEndpoint:
    """Tests for GET /api/v1/projects/{projectId}/analyses."""

    @pytest.mark.asyncio
    async def test_returns_paginated_analyses(self, client):
        tenant = _make_tenant()
        analyses = [_make_analysis(), _make_analysis(analysis_id="ana_test456")]
        mock1, mock2, mock3, mock4 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3, mock4:
            with patch.object(
                analysis_service,
                "list_analyses",
                new_callable=AsyncMock,
                return_value=(analyses, 2),
            ):
                resp = await client.get("/api/v1/projects/p1/analyses")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 2
        assert body["pagination"]["total_count"] == 2
        assert body["pagination"]["page"] == 1

    @pytest.mark.asyncio
    async def test_returns_empty_list(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3, mock4 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3, mock4:
            with patch.object(
                analysis_service,
                "list_analyses",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get("/api/v1/projects/p1/analyses")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0
        assert body["pagination"]["total_count"] == 0

    @pytest.mark.asyncio
    async def test_passes_pagination_params(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3, mock4 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3, mock4:
            with patch.object(
                analysis_service,
                "list_analyses",
                new_callable=AsyncMock,
                return_value=([], 0),
            ) as mock_list:
                resp = await client.get(
                    "/api/v1/projects/p1/analyses?page=2&pageSize=10"
                )

        assert resp.status_code == 200
        mock_list.assert_awaited_once()
        call_args = mock_list.call_args
        # Should pass tenant_id, project_id, page, page_size
        assert call_args.args[0] == "t-001"  # tenant_id
        assert call_args.args[1] == "p1"     # project_id
        assert call_args.args[2] == 2        # page
        assert call_args.args[3] == 10       # page_size

    @pytest.mark.asyncio
    async def test_returns_401_when_no_tenant_context(self, client):
        resp = await client.get("/api/v1/projects/p1/analyses")
        assert resp.status_code == 401


class TestGetAnalysisEndpoint:
    """Tests for GET /api/v1/projects/{projectId}/analyses/{analysisId}."""

    @pytest.mark.asyncio
    async def test_returns_analysis(self, client):
        tenant = _make_tenant()
        analysis = _make_analysis(status=AnalysisStatus.COMPLETED)
        mock1, mock2, mock3, mock4 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3, mock4:
            with patch.object(
                analysis_service,
                "get_analysis",
                new_callable=AsyncMock,
                return_value=analysis,
            ):
                resp = await client.get("/api/v1/projects/p1/analyses/ana_test123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "ana_test123"
        assert body["data"]["status"] == "completed"

    @pytest.mark.asyncio
    async def test_returns_404_when_not_found(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3, mock4 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3, mock4:
            with patch.object(
                analysis_service,
                "get_analysis",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.get("/api/v1/projects/p1/analyses/ana_missing")

        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "RESOURCE_NOT_FOUND"

    @pytest.mark.asyncio
    async def test_returns_401_when_no_tenant_context(self, client):
        resp = await client.get("/api/v1/projects/p1/analyses/ana_test123")
        assert resp.status_code == 401

    @pytest.mark.asyncio
    async def test_includes_result_when_completed(self, client):
        tenant = _make_tenant()
        result = AnalysisResult(
            response="The main patterns are...",
            toolCalls=[],
            retryCount=0,
        )
        analysis = _make_analysis(status=AnalysisStatus.COMPLETED)
        analysis.result = result
        mock1, mock2, mock3, mock4 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3, mock4:
            with patch.object(
                analysis_service,
                "get_analysis",
                new_callable=AsyncMock,
                return_value=analysis,
            ):
                resp = await client.get("/api/v1/projects/p1/analyses/ana_test123")

        assert resp.status_code == 200
        body = resp.json()
        # Response is now flattened
        assert body["data"]["response"] == "The main patterns are..."


class TestAnalysisRoutesRegistered:
    """Verify analysis routes are registered in the FastAPI app."""

    @pytest.mark.asyncio
    async def test_analysis_routes_exist(self, client):
        routes = [r.path for r in app.routes]
        assert "/api/v1/projects/{project_id}/analyses" in routes
        assert "/api/v1/projects/{project_id}/analyses/{analysis_id}" in routes
