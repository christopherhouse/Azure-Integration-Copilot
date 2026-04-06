"""Cosmos DB repository for analysis documents."""

from __future__ import annotations

import structlog
from azure.cosmos.aio import ContainerProxy

from shared.cosmos import cosmos_service

from .models import Analysis

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DATABASE_NAME = "integration-copilot"
CONTAINER_NAME = "analyses"


class AnalysisRepository:
    """Cosmos DB operations for the ``analyses`` container."""

    async def _get_container(self) -> ContainerProxy:
        return await cosmos_service.get_container(DATABASE_NAME, CONTAINER_NAME)

    async def create(self, analysis: Analysis) -> Analysis:
        """Create a new analysis document."""
        container = await self._get_container()
        doc = analysis.model_dump(by_alias=True)
        # Ensure datetime fields are serialised as ISO strings for Cosmos DB
        for field in ("createdAt", "completedAt"):
            val = doc.get(field)
            if val is not None and not isinstance(val, str):
                doc[field] = val.isoformat()
        await container.create_item(body=doc)
        return analysis

    async def get_by_id(self, partition_key: str, analysis_id: str) -> Analysis | None:
        """Get an analysis document by ID."""
        container = await self._get_container()
        try:
            doc = await container.read_item(item=analysis_id, partition_key=partition_key)
            return Analysis.model_validate(doc)
        except Exception:
            return None

    async def update(self, analysis: Analysis) -> Analysis:
        """Update an analysis document (full replace)."""
        container = await self._get_container()
        doc = analysis.model_dump(by_alias=True)
        for field in ("createdAt", "completedAt"):
            val = doc.get(field)
            if val is not None and not isinstance(val, str):
                doc[field] = val.isoformat()
        await container.upsert_item(body=doc)
        return analysis

    async def list_by_project(
        self,
        partition_key: str,
        page: int = 1,
        page_size: int = 20,
    ) -> tuple[list[Analysis], int]:
        """List analyses for a project (paginated, newest first)."""
        container = await self._get_container()

        where_clause = "WHERE c.partitionKey = @pk AND c.type = 'analysis'"
        params: list[dict] = [{"name": "@pk", "value": partition_key}]

        # Count
        count_query = f"SELECT VALUE COUNT(1) FROM c {where_clause}"
        total_count = 0
        async for item in container.query_items(query=count_query, parameters=params):
            total_count = item

        # Data
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
        analyses: list[Analysis] = []
        async for item in container.query_items(query=data_query, parameters=data_params):
            analyses.append(Analysis.model_validate(item))

        return analyses, total_count

    async def count_today(self, partition_key: str, since_iso: str) -> int:
        """Count analyses created since a given ISO timestamp (for quota)."""
        container = await self._get_container()
        query = (
            "SELECT VALUE COUNT(1) FROM c "
            "WHERE c.partitionKey = @pk AND c.type = 'analysis' "
            "AND c.createdAt >= @since"
        )
        params = [
            {"name": "@pk", "value": partition_key},
            {"name": "@since", "value": since_iso},
        ]
        async for item in container.query_items(query=query, parameters=params):
            return item
        return 0


analysis_repository = AnalysisRepository()
