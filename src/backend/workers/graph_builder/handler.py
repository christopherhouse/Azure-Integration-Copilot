"""Graph builder worker handler — transforms parse results into graph data."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import structlog
from ulid import ULID

from domains.artifacts.models import ArtifactError, ArtifactStatus
from domains.artifacts.repository import ArtifactRepository
from domains.graph.id_generation import generate_component_id, generate_edge_id
from domains.graph.repository import GraphRepository
from domains.projects.repository import ProjectRepository
from shared.cosmos import CosmosService
from shared.event_types import EVENT_GRAPH_BUILD_FAILED, EVENT_GRAPH_UPDATED
from shared.events import EventGridPublisher, build_cloud_event
from workers.base import PermanentError, TransientError, WorkerHandler

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DATABASE_NAME = "integration-copilot"
PROJECTS_CONTAINER = "projects"

# Statuses indicating the artifact has already progressed past graph building.
_POST_GRAPH_STATUSES: frozenset[ArtifactStatus] = frozenset(
    {
        ArtifactStatus.GRAPH_BUILT,
        ArtifactStatus.GRAPH_FAILED,
    }
)


class GraphBuilderHandler(WorkerHandler):
    """Process ``ArtifactParsed`` events by building graph data from parse results."""

    def __init__(
        self,
        artifact_repository: ArtifactRepository,
        graph_repository: GraphRepository,
        project_repository: ProjectRepository,
        cosmos_service: CosmosService,
        event_publisher: EventGridPublisher,
    ) -> None:
        self._artifact_repo = artifact_repository
        self._graph_repo = graph_repository
        self._project_repo = project_repository
        self._cosmos = cosmos_service
        self._publisher = event_publisher

    # -- WorkerHandler interface -----------------------------------------------

    async def is_already_processed(self, event_data: dict[str, Any]) -> bool:
        """Return ``True`` if the artifact has already been graph-built or failed."""
        tenant_id = event_data["tenantId"]
        artifact_id = event_data["artifactId"]

        artifact = await self._artifact_repo.get_by_id(tenant_id, artifact_id)
        if artifact is None:
            return False

        return artifact.status in _POST_GRAPH_STATUSES

    async def handle(self, event_data: dict[str, Any]) -> None:
        """Build graph from parse result: parsed → graph_building → graph_built."""
        tenant_id = event_data["tenantId"]
        project_id = event_data["projectId"]
        artifact_id = event_data["artifactId"]
        parse_result_id = event_data.get("parseResultId")

        log = logger.bind(
            tenant_id=tenant_id,
            project_id=project_id,
            artifact_id=artifact_id,
        )

        # parsed → graph_building
        try:
            await self._artifact_repo.update_status(
                tenant_id, artifact_id, ArtifactStatus.GRAPH_BUILDING
            )
        except Exception as exc:
            raise TransientError(f"Failed to transition to graph_building: {exc}") from exc

        # Load parse result from Cosmos DB
        parse_result = await self._load_parse_result(tenant_id, parse_result_id, artifact_id)
        if parse_result is None:
            raise PermanentError(
                f"Parse result not found for artifact {artifact_id}"
            )

        partition_key = f"{tenant_id}:{project_id}"
        now = datetime.now(UTC)

        # Get current project to determine graph version
        project = await self._project_repo.get_by_id(tenant_id, project_id)
        if project is None:
            raise PermanentError(f"Project {project_id} not found for tenant {tenant_id}")
        new_graph_version = project.graph_version + 1

        # Build temp_id → stable_id mapping
        id_map: dict[str, str] = {}

        # Process components
        components = parse_result.get("components", [])
        for comp in components:
            temp_id = comp.get("tempId", "")
            component_type = comp.get("componentType", "")
            name = comp.get("name", "")
            display_name = comp.get("displayName", name)

            stable_id = generate_component_id(tenant_id, project_id, component_type, name)
            id_map[temp_id] = stable_id

            doc = {
                "id": stable_id,
                "partitionKey": partition_key,
                "type": "component",
                "tenantId": tenant_id,
                "projectId": project_id,
                "artifactId": artifact_id,
                "componentType": component_type,
                "name": name,
                "displayName": display_name,
                "properties": comp.get("properties", {}),
                "tags": [],
                "graphVersion": new_graph_version,
                "createdAt": now.isoformat(),
                "updatedAt": now.isoformat(),
            }
            try:
                await self._graph_repo.upsert_component(doc)
            except Exception as exc:
                raise TransientError(f"Failed to upsert component {stable_id}: {exc}") from exc

        # Process external references as components
        external_refs = parse_result.get("externalReferences", [])
        for ref in external_refs:
            temp_id = ref.get("tempId", "")
            component_type = ref.get("componentType", "external_service")
            name = ref.get("name", "")
            display_name = ref.get("displayName", name)

            stable_id = generate_component_id(tenant_id, project_id, component_type, name)
            id_map[temp_id] = stable_id

            doc = {
                "id": stable_id,
                "partitionKey": partition_key,
                "type": "component",
                "tenantId": tenant_id,
                "projectId": project_id,
                "artifactId": artifact_id,
                "componentType": component_type,
                "name": name,
                "displayName": display_name,
                "properties": {"inferredFrom": ref.get("inferredFrom", "")},
                "tags": ["external"],
                "graphVersion": new_graph_version,
                "createdAt": now.isoformat(),
                "updatedAt": now.isoformat(),
            }
            try:
                await self._graph_repo.upsert_component(doc)
            except Exception as exc:
                raise TransientError(f"Failed to upsert external ref {stable_id}: {exc}") from exc

        # Process edges — resolve temp IDs to stable IDs
        edges = parse_result.get("edges", [])
        for edge in edges:
            source_temp_id = edge.get("sourceTempId", "")
            target_temp_id = edge.get("targetTempId", "")
            edge_type = edge.get("edgeType", "")

            source_id = id_map.get(source_temp_id, source_temp_id)
            target_id = id_map.get(target_temp_id, target_temp_id)

            edge_id = generate_edge_id(source_id, target_id, edge_type)
            doc = {
                "id": edge_id,
                "partitionKey": partition_key,
                "type": "edge",
                "tenantId": tenant_id,
                "projectId": project_id,
                "sourceComponentId": source_id,
                "targetComponentId": target_id,
                "edgeType": edge_type,
                "properties": edge.get("properties", {}) or {},
                "artifactId": artifact_id,
                "graphVersion": new_graph_version,
                "createdAt": now.isoformat(),
            }
            try:
                await self._graph_repo.upsert_edge(doc)
            except Exception as exc:
                raise TransientError(f"Failed to upsert edge {edge_id}: {exc}") from exc

        # Compute and upsert graph summary
        try:
            component_counts = await self._graph_repo.count_by_type(partition_key, "component")
            edge_counts = await self._graph_repo.count_by_type(partition_key, "edge")
            total_components = sum(component_counts.values())
            total_edges = sum(edge_counts.values())

            summary_id = f"gs_{partition_key}"
            summary_doc = {
                "id": summary_id,
                "partitionKey": partition_key,
                "type": "graph_summary",
                "tenantId": tenant_id,
                "projectId": project_id,
                "graphVersion": new_graph_version,
                "totalComponents": total_components,
                "totalEdges": total_edges,
                "componentCounts": component_counts,
                "edgeCounts": edge_counts,
                "updatedAt": now.isoformat(),
            }
            await self._graph_repo.upsert_summary(summary_doc)
        except Exception as exc:
            raise TransientError(f"Failed to compute/upsert graph summary: {exc}") from exc

        # Increment project graphVersion
        try:
            project.graph_version = new_graph_version
            await self._project_repo.update(project)
        except Exception as exc:
            raise TransientError(f"Failed to increment project graphVersion: {exc}") from exc

        # graph_building → graph_built
        try:
            await self._artifact_repo.update_status(
                tenant_id, artifact_id, ArtifactStatus.GRAPH_BUILT
            )
        except Exception as exc:
            raise TransientError(f"Failed to transition to graph_built: {exc}") from exc

        # Publish GraphUpdated event
        event = build_cloud_event(
            event_type=EVENT_GRAPH_UPDATED,
            source="/integration-copilot/worker/graph-builder",
            subject=f"tenants/{tenant_id}/projects/{project_id}",
            data={
                "tenantId": tenant_id,
                "projectId": project_id,
                "artifactId": artifact_id,
                "graphVersion": new_graph_version,
                "totalComponents": total_components,
                "totalEdges": total_edges,
            },
        )
        await self._publisher.publish_event(event)
        log.info(
            "graph_built",
            graph_version=new_graph_version,
            components=total_components,
            edges=total_edges,
        )

    async def handle_failure(self, event_data: dict[str, Any], error: Exception) -> None:
        """Transition artifact to ``graph_failed`` on permanent error."""
        tenant_id = event_data["tenantId"]
        artifact_id = event_data["artifactId"]

        try:
            artifact = await self._artifact_repo.get_by_id(tenant_id, artifact_id)
            if artifact is not None and artifact.status not in _POST_GRAPH_STATUSES:
                try:
                    await self._artifact_repo.update_status(
                        tenant_id, artifact_id, ArtifactStatus.GRAPH_FAILED
                    )
                except Exception:
                    artifact.error = ArtifactError(
                        code="GRAPH_BUILD_FAILED",
                        message=str(error),
                        occurredAt=datetime.now(UTC),
                    )
                    await self._artifact_repo.update(artifact)

            # Publish GraphBuildFailed event
            event = build_cloud_event(
                event_type=EVENT_GRAPH_BUILD_FAILED,
                source="/integration-copilot/worker/graph-builder",
                subject=(
                    f"tenants/{tenant_id}/projects/{event_data.get('projectId', 'unknown')}"
                    f"/artifacts/{artifact_id}"
                ),
                data={
                    "tenantId": tenant_id,
                    "projectId": event_data.get("projectId"),
                    "artifactId": artifact_id,
                    "error": str(error),
                },
            )
            await self._publisher.publish_event(event)
        except Exception:
            logger.error("handle_failure_error", artifact_id=artifact_id, exc_info=True)

    # -- Private helpers -------------------------------------------------------

    async def _load_parse_result(
        self,
        tenant_id: str,
        parse_result_id: str | None,
        artifact_id: str,
    ) -> dict | None:
        """Load parse result from the projects container in Cosmos DB."""
        container = await self._cosmos.get_container(DATABASE_NAME, PROJECTS_CONTAINER)

        # Try by parse_result_id first
        if parse_result_id:
            try:
                doc = await container.read_item(item=parse_result_id, partition_key=tenant_id)
                if doc.get("type") == "parse_result":
                    return doc
            except Exception:
                logger.warning("parse_result_not_found_by_id", parse_result_id=parse_result_id)

        # Fallback: query by artifactId
        query = (
            "SELECT * FROM c WHERE c.partitionKey = @tenantId "
            "AND c.type = 'parse_result' AND c.artifactId = @artifactId "
            "ORDER BY c.parsedAt DESC OFFSET 0 LIMIT 1"
        )
        params = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@artifactId", "value": artifact_id},
        ]
        async for item in container.query_items(query=query, parameters=params):
            return item

        return None
