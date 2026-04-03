"""Graph domain service — business logic for graph queries."""

from __future__ import annotations

import structlog

from .models import (
    Component,
    ComponentResponse,
    Edge,
    EdgeResponse,
    GraphSummary,
    GraphSummaryResponse,
    NeighborResponse,
)
from .repository import graph_repository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _partition_key(tenant_id: str, project_id: str) -> str:
    return f"{tenant_id}:{project_id}"


class GraphService:
    """Wraps graph repository calls with partition key construction."""

    async def get_summary(
        self, tenant_id: str, project_id: str
    ) -> GraphSummaryResponse | None:
        """Get the graph summary for a project."""
        pk = _partition_key(tenant_id, project_id)
        summary = await graph_repository.get_summary(pk)
        if summary is None:
            return None
        return GraphSummaryResponse.from_summary(summary)

    async def list_components(
        self,
        tenant_id: str,
        project_id: str,
        page: int = 1,
        page_size: int = 20,
        component_type: str | None = None,
    ) -> tuple[list[ComponentResponse], int]:
        """List components for a project (paginated)."""
        pk = _partition_key(tenant_id, project_id)
        components, total = await graph_repository.list_components(
            pk, page, page_size, component_type
        )
        return [ComponentResponse.from_component(c) for c in components], total

    async def get_component(
        self, tenant_id: str, project_id: str, component_id: str
    ) -> ComponentResponse | None:
        """Get a single component by ID."""
        pk = _partition_key(tenant_id, project_id)
        component = await graph_repository.get_component(pk, component_id)
        if component is None:
            return None
        return ComponentResponse.from_component(component)

    async def get_neighbors(
        self,
        tenant_id: str,
        project_id: str,
        component_id: str,
        direction: str = "both",
    ) -> list[NeighborResponse]:
        """Get neighboring components connected by edges."""
        pk = _partition_key(tenant_id, project_id)
        raw = await graph_repository.get_neighbors(pk, component_id, direction)
        return [
            NeighborResponse(
                edge=EdgeResponse.from_edge(n["edge"]),
                component=ComponentResponse.from_component(n["component"]),
                direction=n["direction"],
            )
            for n in raw
        ]

    async def list_edges(
        self, tenant_id: str, project_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[EdgeResponse], int]:
        """List edges for a project (paginated)."""
        pk = _partition_key(tenant_id, project_id)
        edges, total = await graph_repository.list_edges(pk, page, page_size)
        return [EdgeResponse.from_edge(e) for e in edges], total


graph_service = GraphService()
