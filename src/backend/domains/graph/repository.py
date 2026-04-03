"""Cosmos DB repository for graph documents (components, edges, summaries)."""

from __future__ import annotations

import structlog
from azure.cosmos.aio import ContainerProxy

from shared.cosmos import cosmos_service

from .models import Component, Edge, GraphSummary

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DATABASE_NAME = "integration-copilot"
CONTAINER_NAME = "graph"


class GraphRepository:
    """Cosmos DB operations for the ``graph`` container."""

    async def _get_container(self) -> ContainerProxy:
        return await cosmos_service.get_container(DATABASE_NAME, CONTAINER_NAME)

    # -- Component operations -------------------------------------------------

    async def upsert_component(self, doc: dict) -> dict:
        """Upsert a component document."""
        container = await self._get_container()
        result = await container.upsert_item(body=doc)
        return result

    async def get_component(
        self, partition_key: str, component_id: str
    ) -> Component | None:
        """Get a single component by ID."""
        container = await self._get_container()
        try:
            doc = await container.read_item(item=component_id, partition_key=partition_key)
            if doc.get("type") != "component":
                return None
            return Component.model_validate(doc)
        except Exception:
            return None

    async def list_components(
        self,
        partition_key: str,
        page: int = 1,
        page_size: int = 20,
        component_type: str | None = None,
    ) -> tuple[list[Component], int]:
        """List components for a project (paginated, optionally filtered by type)."""
        container = await self._get_container()

        where_clause = "WHERE c.partitionKey = @pk AND c.type = 'component'"
        params: list[dict] = [{"name": "@pk", "value": partition_key}]

        if component_type:
            where_clause += " AND c.componentType = @componentType"
            params.append({"name": "@componentType", "value": component_type})

        # Count query
        count_query = f"SELECT VALUE COUNT(1) FROM c {where_clause}"
        total_count = 0
        async for item in container.query_items(query=count_query, parameters=params):
            total_count = item

        # Data query with OFFSET/LIMIT
        offset = (page - 1) * page_size
        data_query = (
            f"SELECT * FROM c {where_clause} "
            "ORDER BY c.name ASC "
            "OFFSET @offset LIMIT @limit"
        )
        data_params = [
            *params,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": page_size},
        ]
        components: list[Component] = []
        async for item in container.query_items(query=data_query, parameters=data_params):
            components.append(Component.model_validate(item))

        return components, total_count

    async def get_neighbors(
        self,
        partition_key: str,
        component_id: str,
        direction: str = "both",
    ) -> list[dict]:
        """Get neighboring components connected by edges.

        Returns a list of dicts with ``edge``, ``component``, and ``direction`` keys.
        """
        container = await self._get_container()
        results: list[dict] = []

        # Outgoing edges (component is source)
        if direction in ("both", "outgoing"):
            query = (
                "SELECT * FROM c WHERE c.partitionKey = @pk "
                "AND c.type = 'edge' AND c.sourceComponentId = @componentId"
            )
            params = [
                {"name": "@pk", "value": partition_key},
                {"name": "@componentId", "value": component_id},
            ]
            async for item in container.query_items(query=query, parameters=params):
                edge = Edge.model_validate(item)
                target = await self.get_component(partition_key, edge.target_component_id)
                if target:
                    results.append({"edge": edge, "component": target, "direction": "outgoing"})

        # Incoming edges (component is target)
        if direction in ("both", "incoming"):
            query = (
                "SELECT * FROM c WHERE c.partitionKey = @pk "
                "AND c.type = 'edge' AND c.targetComponentId = @componentId"
            )
            params = [
                {"name": "@pk", "value": partition_key},
                {"name": "@componentId", "value": component_id},
            ]
            async for item in container.query_items(query=query, parameters=params):
                edge = Edge.model_validate(item)
                source = await self.get_component(partition_key, edge.source_component_id)
                if source:
                    results.append({"edge": edge, "component": source, "direction": "incoming"})

        return results

    # -- Edge operations ------------------------------------------------------

    async def upsert_edge(self, doc: dict) -> dict:
        """Upsert an edge document."""
        container = await self._get_container()
        result = await container.upsert_item(body=doc)
        return result

    async def list_edges(
        self, partition_key: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Edge], int]:
        """List edges for a project (paginated)."""
        container = await self._get_container()

        where_clause = "WHERE c.partitionKey = @pk AND c.type = 'edge'"
        params: list[dict] = [{"name": "@pk", "value": partition_key}]

        # Count query
        count_query = f"SELECT VALUE COUNT(1) FROM c {where_clause}"
        total_count = 0
        async for item in container.query_items(query=count_query, parameters=params):
            total_count = item

        # Data query
        offset = (page - 1) * page_size
        data_query = (
            f"SELECT * FROM c {where_clause} "
            "ORDER BY c.createdAt DESC "
            "OFFSET @offset LIMIT @limit"
        )
        data_params = [
            *params,
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": page_size},
        ]
        edges: list[Edge] = []
        async for item in container.query_items(query=data_query, parameters=data_params):
            edges.append(Edge.model_validate(item))

        return edges, total_count

    # -- Summary operations ---------------------------------------------------

    async def upsert_summary(self, doc: dict) -> dict:
        """Upsert a graph summary document."""
        container = await self._get_container()
        result = await container.upsert_item(body=doc)
        return result

    async def get_summary(self, partition_key: str) -> GraphSummary | None:
        """Get the graph summary for a project."""
        container = await self._get_container()

        query = (
            "SELECT * FROM c WHERE c.partitionKey = @pk AND c.type = 'graph_summary'"
        )
        params = [{"name": "@pk", "value": partition_key}]
        async for item in container.query_items(query=query, parameters=params):
            return GraphSummary.model_validate(item)
        return None

    # -- Deletion helpers -----------------------------------------------------

    async def delete_all_by_project(self, partition_key: str) -> int:
        """Hard-delete all graph documents (components, edges, summaries) for a project.

        Returns the number of documents deleted.
        """
        container = await self._get_container()

        query = "SELECT c.id FROM c WHERE c.partitionKey = @pk"
        params = [{"name": "@pk", "value": partition_key}]

        doc_ids: list[str] = []
        async for item in container.query_items(query=query, parameters=params):
            doc_ids.append(item["id"])

        count = 0
        for doc_id in doc_ids:
            try:
                await container.delete_item(item=doc_id, partition_key=partition_key)
                count += 1
            except Exception:
                # Best-effort: log and continue so that a single failing
                # document does not abort deletion of the remaining graph data.
                logger.warning(
                    "failed_to_delete_graph_doc",
                    doc_id=doc_id,
                    partition_key=partition_key,
                )

        logger.info(
            "graph_docs_deleted_for_project",
            partition_key=partition_key,
            count=count,
        )
        return count

    # -- Aggregation helpers --------------------------------------------------

    async def count_by_type(self, partition_key: str, doc_type: str) -> dict[str, int]:
        """Count documents of a given type grouped by their subtype field.

        For ``component`` documents, groups by ``componentType``.
        For ``edge`` documents, groups by ``edgeType``.
        """
        container = await self._get_container()
        type_field = "componentType" if doc_type == "component" else "edgeType"

        query = (
            f"SELECT c.{type_field} AS subtype, COUNT(1) AS cnt FROM c "
            f"WHERE c.partitionKey = @pk AND c.type = @docType "
            f"GROUP BY c.{type_field}"
        )
        params = [
            {"name": "@pk", "value": partition_key},
            {"name": "@docType", "value": doc_type},
        ]
        counts: dict[str, int] = {}
        async for item in container.query_items(query=query, parameters=params):
            counts[item["subtype"]] = item["cnt"]
        return counts


graph_repository = GraphRepository()
