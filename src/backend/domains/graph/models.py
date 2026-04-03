"""Graph domain models for API responses and Cosmos DB documents."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Cosmos DB document models
# ---------------------------------------------------------------------------


class Component(BaseModel):
    """Component document stored in the ``graph`` Cosmos DB container."""

    id: str
    partition_key: str = Field(alias="partitionKey")
    type: str = "component"
    tenant_id: str = Field(alias="tenantId")
    project_id: str = Field(alias="projectId")
    artifact_id: str = Field(alias="artifactId")
    component_type: str = Field(alias="componentType")
    name: str
    display_name: str = Field(alias="displayName")
    properties: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    graph_version: int = Field(alias="graphVersion")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="updatedAt")

    model_config = {"populate_by_name": True}


class Edge(BaseModel):
    """Edge document stored in the ``graph`` Cosmos DB container."""

    id: str
    partition_key: str = Field(alias="partitionKey")
    type: str = "edge"
    tenant_id: str = Field(alias="tenantId")
    project_id: str = Field(alias="projectId")
    source_component_id: str = Field(alias="sourceComponentId")
    target_component_id: str = Field(alias="targetComponentId")
    edge_type: str = Field(alias="edgeType")
    properties: dict = Field(default_factory=dict)
    artifact_id: str = Field(alias="artifactId")
    graph_version: int = Field(alias="graphVersion")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")

    model_config = {"populate_by_name": True}


class GraphSummary(BaseModel):
    """Graph summary document stored in the ``graph`` Cosmos DB container."""

    id: str
    partition_key: str = Field(alias="partitionKey")
    type: str = "graph_summary"
    tenant_id: str = Field(alias="tenantId")
    project_id: str = Field(alias="projectId")
    graph_version: int = Field(alias="graphVersion")
    total_components: int = Field(alias="totalComponents")
    total_edges: int = Field(alias="totalEdges")
    component_counts: dict[str, int] = Field(default_factory=dict, alias="componentCounts")
    edge_counts: dict[str, int] = Field(default_factory=dict, alias="edgeCounts")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="updatedAt")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# API response models
# ---------------------------------------------------------------------------


class ComponentResponse(BaseModel):
    """Component data returned in API responses."""

    id: str
    component_type: str = Field(alias="componentType")
    name: str
    display_name: str = Field(alias="displayName")
    properties: dict = Field(default_factory=dict)
    tags: list[str] = Field(default_factory=list)
    artifact_id: str = Field(alias="artifactId")
    graph_version: int = Field(alias="graphVersion")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_component(cls, component: Component) -> ComponentResponse:
        """Build a response from a Component domain model."""
        return cls(
            id=component.id,
            componentType=component.component_type,
            name=component.name,
            displayName=component.display_name,
            properties=component.properties,
            tags=component.tags,
            artifactId=component.artifact_id,
            graphVersion=component.graph_version,
            createdAt=component.created_at,
            updatedAt=component.updated_at,
        )


class EdgeResponse(BaseModel):
    """Edge data returned in API responses."""

    id: str
    source_component_id: str = Field(alias="sourceComponentId")
    target_component_id: str = Field(alias="targetComponentId")
    edge_type: str = Field(alias="edgeType")
    properties: dict = Field(default_factory=dict)
    artifact_id: str = Field(alias="artifactId")
    graph_version: int = Field(alias="graphVersion")
    created_at: datetime = Field(alias="createdAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_edge(cls, edge: Edge) -> EdgeResponse:
        """Build a response from an Edge domain model."""
        return cls(
            id=edge.id,
            sourceComponentId=edge.source_component_id,
            targetComponentId=edge.target_component_id,
            edgeType=edge.edge_type,
            properties=edge.properties,
            artifactId=edge.artifact_id,
            graphVersion=edge.graph_version,
            createdAt=edge.created_at,
        )


class GraphSummaryResponse(BaseModel):
    """Graph summary data returned in API responses."""

    graph_version: int = Field(alias="graphVersion")
    total_components: int = Field(alias="totalComponents")
    total_edges: int = Field(alias="totalEdges")
    component_counts: dict[str, int] = Field(alias="componentCounts")
    edge_counts: dict[str, int] = Field(alias="edgeCounts")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_summary(cls, summary: GraphSummary) -> GraphSummaryResponse:
        """Build a response from a GraphSummary domain model."""
        return cls(
            graphVersion=summary.graph_version,
            totalComponents=summary.total_components,
            totalEdges=summary.total_edges,
            componentCounts=summary.component_counts,
            edgeCounts=summary.edge_counts,
            updatedAt=summary.updated_at,
        )


class NeighborResponse(BaseModel):
    """Neighbor data for a component, including the edge and connected component."""

    edge: EdgeResponse
    component: ComponentResponse
    direction: str  # "incoming" or "outgoing"
