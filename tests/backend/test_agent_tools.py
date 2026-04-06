"""Tests for analysis agent custom tools (scoped to tenant/project)."""

import json
import os
from datetime import UTC, datetime
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
    from domains.graph.models import Component, Edge, GraphSummary
    from workers.analysis.tools.scoping import AnalysisContext, analysis_context
    from workers.analysis.tools.get_project_summary import get_project_summary
    from workers.analysis.tools.get_graph_neighbors import get_graph_neighbors
    from workers.analysis.tools.get_component_details import get_component_details
    from workers.analysis.tools.run_impact_analysis import run_impact_analysis


def _make_component(
    component_id: str = "cmp_001",
    name: str = "order-processor",
    component_type: str = "logic_app_workflow",
    tenant_id: str = "t1",
    project_id: str = "p1",
) -> Component:
    now = datetime.now(UTC)
    return Component(
        id=component_id,
        partitionKey=f"{tenant_id}:{project_id}",
        tenantId=tenant_id,
        projectId=project_id,
        artifactId="art_001",
        componentType=component_type,
        name=name,
        displayName=name.replace("-", " ").title(),
        properties={"triggerType": "http"},
        tags=["production"],
        graphVersion=1,
        createdAt=now,
        updatedAt=now,
    )


def _make_edge(
    edge_id: str = "edg_001",
    source_id: str = "cmp_001",
    target_id: str = "cmp_002",
    edge_type: str = "calls",
    tenant_id: str = "t1",
    project_id: str = "p1",
) -> Edge:
    now = datetime.now(UTC)
    return Edge(
        id=edge_id,
        partitionKey=f"{tenant_id}:{project_id}",
        tenantId=tenant_id,
        projectId=project_id,
        sourceComponentId=source_id,
        targetComponentId=target_id,
        edgeType=edge_type,
        properties={"method": "POST"},
        artifactId="art_001",
        graphVersion=1,
        createdAt=now,
    )


def _make_summary(
    tenant_id: str = "t1",
    project_id: str = "p1",
) -> GraphSummary:
    now = datetime.now(UTC)
    return GraphSummary(
        id="summary_001",
        partitionKey=f"{tenant_id}:{project_id}",
        tenantId=tenant_id,
        projectId=project_id,
        graphVersion=3,
        totalComponents=10,
        totalEdges=8,
        componentCounts={"logic_app_workflow": 3, "api_operation": 5, "external_service": 2},
        edgeCounts={"calls": 5, "has_operation": 3},
        updatedAt=now,
    )


@pytest.fixture(autouse=True)
def _set_analysis_context():
    """Set the analysis context for all tool tests."""
    ctx = AnalysisContext(tenant_id="t1", project_id="p1")
    token = analysis_context.set(ctx)
    yield
    analysis_context.reset(token)


class TestGetProjectSummary:
    """Tests for get_project_summary."""

    @pytest.mark.asyncio
    async def test_returns_summary_data(self):
        summary = _make_summary()
        with patch(
            "workers.analysis.tools.get_project_summary.graph_repository"
        ) as mock_repo:
            mock_repo.get_summary = AsyncMock(return_value=summary)
            result = await get_project_summary()

        data = json.loads(result)
        assert data["totalComponents"] == 10
        assert data["totalEdges"] == 8
        assert data["graphVersion"] == 3
        assert data["componentCounts"]["logic_app_workflow"] == 3

    @pytest.mark.asyncio
    async def test_returns_error_when_no_graph_data(self):
        with patch(
            "workers.analysis.tools.get_project_summary.graph_repository"
        ) as mock_repo:
            mock_repo.get_summary = AsyncMock(return_value=None)
            result = await get_project_summary()

        data = json.loads(result)
        assert "error" in data
        assert "No graph data" in data["error"]

    @pytest.mark.asyncio
    async def test_uses_correct_partition_key(self):
        summary = _make_summary()
        with patch(
            "workers.analysis.tools.get_project_summary.graph_repository"
        ) as mock_repo:
            mock_repo.get_summary = AsyncMock(return_value=summary)
            await get_project_summary()

        mock_repo.get_summary.assert_awaited_once_with("t1:p1")


class TestGetGraphNeighbors:
    """Tests for get_graph_neighbors."""

    @pytest.mark.asyncio
    async def test_returns_neighbors(self):
        component = _make_component(component_id="cmp_002", name="email-sender")
        edge = _make_edge()
        neighbors = [
            {"edge": edge, "component": component, "direction": "outgoing"}
        ]
        with patch(
            "workers.analysis.tools.get_graph_neighbors.graph_repository"
        ) as mock_repo:
            mock_repo.get_neighbors = AsyncMock(return_value=neighbors)
            result = await get_graph_neighbors(component_id="cmp_001")

        data = json.loads(result)
        assert data["count"] == 1
        assert data["neighbors"][0]["direction"] == "outgoing"
        assert data["neighbors"][0]["component"]["id"] == "cmp_002"
        assert data["neighbors"][0]["component"]["name"] == "email-sender"
        assert data["neighbors"][0]["edge"]["edgeType"] == "calls"

    @pytest.mark.asyncio
    async def test_returns_empty_when_no_neighbors(self):
        with patch(
            "workers.analysis.tools.get_graph_neighbors.graph_repository"
        ) as mock_repo:
            mock_repo.get_neighbors = AsyncMock(return_value=[])
            result = await get_graph_neighbors(component_id="cmp_isolated")

        data = json.loads(result)
        assert data["count"] == 0
        assert data["neighbors"] == []

    @pytest.mark.asyncio
    async def test_passes_direction_to_repository(self):
        with patch(
            "workers.analysis.tools.get_graph_neighbors.graph_repository"
        ) as mock_repo:
            mock_repo.get_neighbors = AsyncMock(return_value=[])
            await get_graph_neighbors(
                component_id="cmp_001", direction="incoming"
            )

        mock_repo.get_neighbors.assert_awaited_once_with("t1:p1", "cmp_001", "incoming")

    @pytest.mark.asyncio
    async def test_defaults_direction_to_both(self):
        with patch(
            "workers.analysis.tools.get_graph_neighbors.graph_repository"
        ) as mock_repo:
            mock_repo.get_neighbors = AsyncMock(return_value=[])
            await get_graph_neighbors(component_id="cmp_001")

        mock_repo.get_neighbors.assert_awaited_once_with("t1:p1", "cmp_001", "both")


class TestGetComponentDetails:
    """Tests for get_component_details."""

    @pytest.mark.asyncio
    async def test_returns_component_details(self):
        component = _make_component()
        with patch(
            "workers.analysis.tools.get_component_details.graph_repository"
        ) as mock_repo:
            mock_repo.get_component = AsyncMock(return_value=component)
            result = await get_component_details(component_id="cmp_001")

        data = json.loads(result)
        assert data["id"] == "cmp_001"
        assert data["name"] == "order-processor"
        assert data["componentType"] == "logic_app_workflow"
        assert data["properties"]["triggerType"] == "http"
        assert data["tags"] == ["production"]

    @pytest.mark.asyncio
    async def test_returns_error_when_not_found(self):
        with patch(
            "workers.analysis.tools.get_component_details.graph_repository"
        ) as mock_repo:
            mock_repo.get_component = AsyncMock(return_value=None)
            result = await get_component_details(component_id="cmp_missing")

        data = json.loads(result)
        assert "error" in data
        assert "cmp_missing" in data["error"]

    @pytest.mark.asyncio
    async def test_uses_correct_partition_key(self):
        component = _make_component()
        with patch(
            "workers.analysis.tools.get_component_details.graph_repository"
        ) as mock_repo:
            mock_repo.get_component = AsyncMock(return_value=component)
            await get_component_details(component_id="cmp_001")

        mock_repo.get_component.assert_awaited_once_with("t1:p1", "cmp_001")


class TestRunImpactAnalysis:
    """Tests for run_impact_analysis."""

    @pytest.mark.asyncio
    async def test_bfs_traversal_downstream(self):
        """Test BFS finds all downstream dependencies."""
        comp_a = _make_component(component_id="cmp_a", name="service-a")
        comp_b = _make_component(component_id="cmp_b", name="service-b")
        comp_c = _make_component(component_id="cmp_c", name="service-c")
        root = _make_component(component_id="cmp_root", name="root-service")

        edge_ab = _make_edge(edge_id="edg_ab", source_id="cmp_root", target_id="cmp_a")
        edge_bc = _make_edge(edge_id="edg_bc", source_id="cmp_a", target_id="cmp_b")
        edge_cd = _make_edge(edge_id="edg_cd", source_id="cmp_b", target_id="cmp_c")

        async def mock_get_neighbors(pk, comp_id, direction):
            if comp_id == "cmp_root":
                return [{"edge": edge_ab, "component": comp_a, "direction": "outgoing"}]
            elif comp_id == "cmp_a":
                return [{"edge": edge_bc, "component": comp_b, "direction": "outgoing"}]
            elif comp_id == "cmp_b":
                return [{"edge": edge_cd, "component": comp_c, "direction": "outgoing"}]
            return []

        with patch(
            "workers.analysis.tools.run_impact_analysis.graph_repository"
        ) as mock_repo:
            mock_repo.get_neighbors = AsyncMock(side_effect=mock_get_neighbors)
            mock_repo.get_component = AsyncMock(return_value=root)
            result = await run_impact_analysis(
                component_id="cmp_root", direction="downstream", max_depth=3
            )

        data = json.loads(result)
        assert data["totalImpacted"] == 3
        assert data["direction"] == "downstream"
        assert data["rootComponent"]["id"] == "cmp_root"

        impacted_ids = [c["id"] for c in data["impactedComponents"]]
        assert "cmp_a" in impacted_ids
        assert "cmp_b" in impacted_ids
        assert "cmp_c" in impacted_ids

    @pytest.mark.asyncio
    async def test_respects_max_depth(self):
        """Traversal should stop at max_depth."""
        comp_a = _make_component(component_id="cmp_a", name="service-a")
        comp_b = _make_component(component_id="cmp_b", name="service-b")
        root = _make_component(component_id="cmp_root", name="root-service")

        edge_ab = _make_edge(source_id="cmp_root", target_id="cmp_a")
        edge_bc = _make_edge(edge_id="edg_bc", source_id="cmp_a", target_id="cmp_b")

        async def mock_get_neighbors(pk, comp_id, direction):
            if comp_id == "cmp_root":
                return [{"edge": edge_ab, "component": comp_a, "direction": "outgoing"}]
            elif comp_id == "cmp_a":
                return [{"edge": edge_bc, "component": comp_b, "direction": "outgoing"}]
            return []

        with patch(
            "workers.analysis.tools.run_impact_analysis.graph_repository"
        ) as mock_repo:
            mock_repo.get_neighbors = AsyncMock(side_effect=mock_get_neighbors)
            mock_repo.get_component = AsyncMock(return_value=root)
            result = await run_impact_analysis(
                component_id="cmp_root", direction="downstream", max_depth=1
            )

        data = json.loads(result)
        assert data["totalImpacted"] == 1
        assert data["impactedComponents"][0]["id"] == "cmp_a"
        assert data["maxDepth"] == 1

    @pytest.mark.asyncio
    async def test_caps_max_depth_at_5(self):
        """max_depth should be capped at 5 regardless of input."""
        root = _make_component(component_id="cmp_root", name="root-service")

        with patch(
            "workers.analysis.tools.run_impact_analysis.graph_repository"
        ) as mock_repo:
            mock_repo.get_neighbors = AsyncMock(return_value=[])
            mock_repo.get_component = AsyncMock(return_value=root)
            result = await run_impact_analysis(
                component_id="cmp_root", direction="downstream", max_depth=100
            )

        data = json.loads(result)
        assert data["maxDepth"] == 5

    @pytest.mark.asyncio
    async def test_upstream_uses_incoming_direction(self):
        """Upstream traversal should query incoming neighbors."""
        root = _make_component(component_id="cmp_root", name="root-service")

        with patch(
            "workers.analysis.tools.run_impact_analysis.graph_repository"
        ) as mock_repo:
            mock_repo.get_neighbors = AsyncMock(return_value=[])
            mock_repo.get_component = AsyncMock(return_value=root)
            await run_impact_analysis(
                component_id="cmp_root", direction="upstream"
            )

        # Should use "incoming" for upstream traversal
        mock_repo.get_neighbors.assert_awaited_with("t1:p1", "cmp_root", "incoming")

    @pytest.mark.asyncio
    async def test_handles_no_impacted_components(self):
        root = _make_component(component_id="cmp_root", name="root-service")

        with patch(
            "workers.analysis.tools.run_impact_analysis.graph_repository"
        ) as mock_repo:
            mock_repo.get_neighbors = AsyncMock(return_value=[])
            mock_repo.get_component = AsyncMock(return_value=root)
            result = await run_impact_analysis(
                component_id="cmp_root", direction="downstream"
            )

        data = json.loads(result)
        assert data["totalImpacted"] == 0
        assert data["impactedComponents"] == []

    @pytest.mark.asyncio
    async def test_avoids_cycles(self):
        """BFS should not revisit already-visited components."""
        comp_a = _make_component(component_id="cmp_a", name="service-a")
        root = _make_component(component_id="cmp_root", name="root-service")

        edge_to_a = _make_edge(source_id="cmp_root", target_id="cmp_a")
        # Edge back to root to create cycle
        edge_back = _make_edge(edge_id="edg_back", source_id="cmp_a", target_id="cmp_root")

        async def mock_get_neighbors(pk, comp_id, direction):
            if comp_id == "cmp_root":
                return [{"edge": edge_to_a, "component": comp_a, "direction": "outgoing"}]
            elif comp_id == "cmp_a":
                return [{"edge": edge_back, "component": root, "direction": "outgoing"}]
            return []

        with patch(
            "workers.analysis.tools.run_impact_analysis.graph_repository"
        ) as mock_repo:
            mock_repo.get_neighbors = AsyncMock(side_effect=mock_get_neighbors)
            mock_repo.get_component = AsyncMock(return_value=root)
            result = await run_impact_analysis(
                component_id="cmp_root", direction="downstream", max_depth=5
            )

        data = json.loads(result)
        # Root is excluded from impacted (it's the starting node)
        # cmp_a is impacted, but root should NOT reappear
        assert data["totalImpacted"] == 1
        assert data["impactedComponents"][0]["id"] == "cmp_a"

    @pytest.mark.asyncio
    async def test_includes_depth_in_impacted_components(self):
        comp_a = _make_component(component_id="cmp_a", name="service-a")
        comp_b = _make_component(component_id="cmp_b", name="service-b")
        root = _make_component(component_id="cmp_root", name="root-service")

        edge_to_a = _make_edge(source_id="cmp_root", target_id="cmp_a")
        edge_to_b = _make_edge(edge_id="edg_ab", source_id="cmp_a", target_id="cmp_b")

        async def mock_get_neighbors(pk, comp_id, direction):
            if comp_id == "cmp_root":
                return [{"edge": edge_to_a, "component": comp_a, "direction": "outgoing"}]
            elif comp_id == "cmp_a":
                return [{"edge": edge_to_b, "component": comp_b, "direction": "outgoing"}]
            return []

        with patch(
            "workers.analysis.tools.run_impact_analysis.graph_repository"
        ) as mock_repo:
            mock_repo.get_neighbors = AsyncMock(side_effect=mock_get_neighbors)
            mock_repo.get_component = AsyncMock(return_value=root)
            result = await run_impact_analysis(
                component_id="cmp_root", direction="downstream", max_depth=3
            )

        data = json.loads(result)
        impacted = {c["id"]: c["depth"] for c in data["impactedComponents"]}
        assert impacted["cmp_a"] == 1
        assert impacted["cmp_b"] == 2
