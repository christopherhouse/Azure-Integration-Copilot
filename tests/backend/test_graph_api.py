"""Tests for graph query API endpoints."""

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
    from domains.graph.models import (
        ComponentResponse,
        EdgeResponse,
        GraphSummaryResponse,
        NeighborResponse,
    )
    from domains.graph.service import graph_service
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


def _make_summary_response() -> GraphSummaryResponse:
    return GraphSummaryResponse(
        graphVersion=3,
        totalComponents=10,
        totalEdges=8,
        componentCounts={"logic_app_workflow": 3, "api_operation": 5, "external_service": 2},
        edgeCounts={"calls": 5, "has_operation": 3},
        updatedAt=datetime(2026, 3, 25, 14, 35, 0, tzinfo=UTC),
    )


def _make_component_response(
    component_id: str = "cmp_test123",
    component_type: str = "logic_app_workflow",
    name: str = "order-processor",
) -> ComponentResponse:
    return ComponentResponse(
        id=component_id,
        componentType=component_type,
        name=name,
        displayName=name.replace("-", " ").title(),
        properties={"triggerType": "http"},
        tags=[],
        artifactId="art_test123",
        graphVersion=3,
        createdAt=datetime(2026, 3, 25, 14, 32, 0, tzinfo=UTC),
        updatedAt=datetime(2026, 3, 25, 14, 32, 0, tzinfo=UTC),
    )


def _make_edge_response(
    edge_id: str = "edg_test123",
    source_id: str = "cmp_src",
    target_id: str = "cmp_tgt",
) -> EdgeResponse:
    return EdgeResponse(
        id=edge_id,
        sourceComponentId=source_id,
        targetComponentId=target_id,
        edgeType="calls",
        properties={"method": "POST"},
        artifactId="art_test123",
        graphVersion=3,
        createdAt=datetime(2026, 3, 25, 14, 32, 0, tzinfo=UTC),
    )


class TestGraphSummaryEndpoint:
    """Tests for GET /api/v1/projects/{projectId}/graph/summary."""

    @pytest.mark.asyncio
    async def test_returns_summary(self, client):
        tenant = _make_tenant()
        summary = _make_summary_response()
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(graph_service, "get_summary", new_callable=AsyncMock, return_value=summary):
                resp = await client.get("/api/v1/projects/p1/graph/summary")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["totalComponents"] == 10
        assert body["data"]["totalEdges"] == 8
        assert body["data"]["graphVersion"] == 3
        assert "logic_app_workflow" in body["data"]["componentCounts"]

    @pytest.mark.asyncio
    async def test_returns_404_when_no_summary(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(graph_service, "get_summary", new_callable=AsyncMock, return_value=None):
                resp = await client.get("/api/v1/projects/p1/graph/summary")

        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "RESOURCE_NOT_FOUND"


class TestListComponentsEndpoint:
    """Tests for GET /api/v1/projects/{projectId}/graph/components."""

    @pytest.mark.asyncio
    async def test_returns_paginated_components(self, client):
        tenant = _make_tenant()
        components = [_make_component_response()]
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                graph_service,
                "list_components",
                new_callable=AsyncMock,
                return_value=(components, 1),
            ):
                resp = await client.get("/api/v1/projects/p1/graph/components")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["name"] == "order-processor"
        assert body["pagination"]["total_count"] == 1

    @pytest.mark.asyncio
    async def test_filters_by_component_type(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                graph_service,
                "list_components",
                new_callable=AsyncMock,
                return_value=([], 0),
            ) as mock_list:
                resp = await client.get(
                    "/api/v1/projects/p1/graph/components?componentType=api_operation"
                )

        assert resp.status_code == 200
        # Verify that component_type filter was passed through
        call_args = mock_list.call_args
        args = call_args.args if call_args.args else ()
        kwargs = call_args.kwargs if call_args.kwargs else {}
        assert (len(args) >= 5 and args[4] == "api_operation") or kwargs.get("component_type") == "api_operation"

    @pytest.mark.asyncio
    async def test_returns_empty_list(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                graph_service,
                "list_components",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get("/api/v1/projects/p1/graph/components")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0
        assert body["pagination"]["total_count"] == 0


class TestGetComponentEndpoint:
    """Tests for GET /api/v1/projects/{projectId}/graph/components/{componentId}."""

    @pytest.mark.asyncio
    async def test_returns_component(self, client):
        tenant = _make_tenant()
        component = _make_component_response()
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                graph_service,
                "get_component",
                new_callable=AsyncMock,
                return_value=component,
            ):
                resp = await client.get("/api/v1/projects/p1/graph/components/cmp_test123")

        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["id"] == "cmp_test123"
        assert body["data"]["componentType"] == "logic_app_workflow"

    @pytest.mark.asyncio
    async def test_returns_404_when_not_found(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                graph_service,
                "get_component",
                new_callable=AsyncMock,
                return_value=None,
            ):
                resp = await client.get("/api/v1/projects/p1/graph/components/cmp_missing")

        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "RESOURCE_NOT_FOUND"


class TestGetNeighborsEndpoint:
    """Tests for GET /api/v1/projects/{projectId}/graph/components/{componentId}/neighbors."""

    @pytest.mark.asyncio
    async def test_returns_neighbors(self, client):
        tenant = _make_tenant()
        neighbors = [
            NeighborResponse(
                edge=_make_edge_response(),
                component=_make_component_response(
                    component_id="cmp_neighbor", name="neighbor-wf"
                ),
                direction="outgoing",
            ),
        ]
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                graph_service,
                "get_neighbors",
                new_callable=AsyncMock,
                return_value=neighbors,
            ):
                resp = await client.get(
                    "/api/v1/projects/p1/graph/components/cmp_test123/neighbors"
                )

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["direction"] == "outgoing"
        assert body["data"][0]["component"]["name"] == "neighbor-wf"

    @pytest.mark.asyncio
    async def test_supports_direction_filter(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                graph_service,
                "get_neighbors",
                new_callable=AsyncMock,
                return_value=[],
            ) as mock_fn:
                resp = await client.get(
                    "/api/v1/projects/p1/graph/components/cmp_test123/neighbors?direction=incoming"
                )

        assert resp.status_code == 200
        # Verify direction was passed
        call_args = mock_fn.call_args
        args = call_args.args if call_args.args else ()
        kwargs = call_args.kwargs if call_args.kwargs else {}
        assert "incoming" in args or kwargs.get("direction") == "incoming"


class TestListEdgesEndpoint:
    """Tests for GET /api/v1/projects/{projectId}/graph/edges."""

    @pytest.mark.asyncio
    async def test_returns_paginated_edges(self, client):
        tenant = _make_tenant()
        edges = [_make_edge_response()]
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                graph_service,
                "list_edges",
                new_callable=AsyncMock,
                return_value=(edges, 1),
            ):
                resp = await client.get("/api/v1/projects/p1/graph/edges")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 1
        assert body["data"][0]["edgeType"] == "calls"
        assert body["pagination"]["total_count"] == 1

    @pytest.mark.asyncio
    async def test_returns_empty_edge_list(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                graph_service,
                "list_edges",
                new_callable=AsyncMock,
                return_value=([], 0),
            ):
                resp = await client.get("/api/v1/projects/p1/graph/edges")

        assert resp.status_code == 200
        body = resp.json()
        assert len(body["data"]) == 0


class TestGraphRouterRegistered:
    """Verify graph routes are registered in the FastAPI app."""

    @pytest.mark.asyncio
    async def test_graph_routes_exist(self, client):
        routes = [r.path for r in app.routes]
        assert "/api/v1/projects/{project_id}/graph/summary" in routes
        assert "/api/v1/projects/{project_id}/graph/components" in routes
        assert "/api/v1/projects/{project_id}/graph/components/{component_id}" in routes
        assert "/api/v1/projects/{project_id}/graph/components/{component_id}/neighbors" in routes
        assert "/api/v1/projects/{project_id}/graph/edges" in routes
