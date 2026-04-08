"""Cosmos DB repository for artifact documents."""

from datetime import UTC, datetime

import structlog
from azure.core import MatchConditions
from azure.cosmos import exceptions as cosmos_exceptions
from azure.cosmos.aio import ContainerProxy

from shared.cosmos import cosmos_service

from .models import Artifact, ArtifactStatus, transition_status

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DATABASE_NAME = "integration-copilot"
CONTAINER_NAME = "projects"


class ArtifactRepository:
    """Cosmos DB operations for artifact documents in the projects container."""

    async def _get_container(self) -> ContainerProxy:
        return await cosmos_service.get_container(DATABASE_NAME, CONTAINER_NAME)

    async def create(self, artifact: Artifact) -> Artifact:
        """Create a new artifact document."""
        container = await self._get_container()
        doc = artifact.model_dump(by_alias=True, mode="json")
        result = await container.create_item(body=doc)
        logger.info(
            "artifact_created",
            artifact_id=artifact.id,
            project_id=artifact.project_id,
            tenant_id=artifact.tenant_id,
        )
        return Artifact.model_validate(result)

    async def get_by_id(self, tenant_id: str, artifact_id: str) -> Artifact | None:
        """Get an artifact by ID, scoped to tenant."""
        container = await self._get_container()
        try:
            doc = await container.read_item(item=artifact_id, partition_key=tenant_id)
            if doc.get("type") != "artifact":
                return None
            artifact = Artifact.model_validate(doc)
            artifact.etag = doc.get("_etag")
            return artifact
        except cosmos_exceptions.CosmosResourceNotFoundError:
            return None

    async def list_by_project(
        self,
        tenant_id: str,
        project_id: str,
        page: int = 1,
        page_size: int = 20,
        status_filter: ArtifactStatus | None = None,
    ) -> tuple[list[Artifact], int]:
        """List artifacts for a project (paginated, excluding deleted)."""
        container = await self._get_container()

        # Build WHERE clause — exclude soft-deleted and quarantined artifacts
        where_clause = (
            "WHERE c.partitionKey = @tenantId AND c.type = 'artifact' "
            "AND c.projectId = @projectId AND (NOT IS_DEFINED(c.deletedAt) OR IS_NULL(c.deletedAt))"
            " AND c.status != @quarantinedStatus"
        )
        params = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@projectId", "value": project_id},
            {"name": "@quarantinedStatus", "value": str(ArtifactStatus.QUARANTINED)},
        ]

        if status_filter is not None:
            where_clause += " AND c.status = @status"
            params.append({"name": "@status", "value": str(status_filter)})

        # Count query
        count_query = f"SELECT VALUE COUNT(1) FROM c {where_clause}"
        total_count = 0
        async for item in container.query_items(query=count_query, parameters=params):
            total_count = item

        # Data query with OFFSET/LIMIT
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
        artifacts: list[Artifact] = []
        async for item in container.query_items(query=data_query, parameters=data_params):
            artifacts.append(Artifact.model_validate(item))

        return artifacts, total_count

    async def update_status(
        self, tenant_id: str, artifact_id: str, target_status: ArtifactStatus
    ) -> Artifact | None:
        """Transition an artifact to a new status (validates the transition)."""
        artifact = await self.get_by_id(tenant_id, artifact_id)
        if artifact is None:
            return None
        transition_status(artifact.status, target_status)
        artifact.status = target_status
        artifact.updated_at = datetime.now(UTC)

        container = await self._get_container()
        doc = artifact.model_dump(by_alias=True, mode="json")
        kwargs: dict = {}
        if artifact.etag:
            kwargs["etag"] = artifact.etag
            kwargs["match_condition"] = MatchConditions.IfNotModified
        result = await container.replace_item(item=artifact.id, body=doc, **kwargs)
        logger.info("artifact_status_updated", artifact_id=artifact_id, new_status=target_status)
        updated = Artifact.model_validate(result)
        updated.etag = result.get("_etag")
        return updated

    async def update(self, artifact: Artifact) -> Artifact:
        """Persist an artifact document (full replace) with optimistic concurrency."""
        container = await self._get_container()
        artifact.updated_at = datetime.now(UTC)
        doc = artifact.model_dump(by_alias=True, mode="json")
        kwargs: dict = {}
        if artifact.etag:
            kwargs["etag"] = artifact.etag
            kwargs["match_condition"] = MatchConditions.IfNotModified
        result = await container.replace_item(item=artifact.id, body=doc, **kwargs)
        logger.info("artifact_updated", artifact_id=artifact.id)
        updated = Artifact.model_validate(result)
        updated.etag = result.get("_etag")
        return updated

    async def soft_delete(self, tenant_id: str, artifact_id: str) -> Artifact | None:
        """Soft-delete an artifact by setting deletedAt timestamp."""
        artifact = await self.get_by_id(tenant_id, artifact_id)
        if artifact is None:
            return None
        artifact.deleted_at = datetime.now(UTC)
        artifact.updated_at = datetime.now(UTC)

        container = await self._get_container()
        doc = artifact.model_dump(by_alias=True, mode="json")
        kwargs: dict = {}
        if artifact.etag:
            kwargs["etag"] = artifact.etag
            kwargs["match_condition"] = MatchConditions.IfNotModified
        result = await container.replace_item(item=artifact.id, body=doc, **kwargs)
        logger.info("artifact_soft_deleted", artifact_id=artifact_id)
        return Artifact.model_validate(result)

    async def hard_delete(self, tenant_id: str, artifact_id: str) -> bool:
        """Permanently delete an artifact document from Cosmos DB.

        Returns ``True`` if the document was deleted, ``False`` if it was not found.
        """
        container = await self._get_container()
        try:
            await container.delete_item(item=artifact_id, partition_key=tenant_id)
            logger.info("artifact_hard_deleted", artifact_id=artifact_id)
            return True
        except cosmos_exceptions.CosmosResourceNotFoundError:
            logger.info("artifact_not_found_for_hard_delete", artifact_id=artifact_id)
            return False

    async def delete_parse_results_by_artifact_id(
        self, tenant_id: str, artifact_id: str
    ) -> int:
        """Hard-delete all parse_result documents linked to a specific artifact.

        Returns the number of documents deleted.
        """
        container = await self._get_container()

        query = (
            "SELECT c.id FROM c WHERE c.partitionKey = @tenantId "
            "AND c.type = 'parse_result' AND c.artifactId = @artifactId"
        )
        params = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@artifactId", "value": artifact_id},
        ]

        doc_ids: list[str] = []
        async for item in container.query_items(query=query, parameters=params):
            doc_ids.append(item["id"])

        count = 0
        for doc_id in doc_ids:
            try:
                await container.delete_item(item=doc_id, partition_key=tenant_id)
                count += 1
            except Exception as exc:
                logger.warning(
                    "failed_to_delete_parse_result",
                    doc_id=doc_id,
                    artifact_id=artifact_id,
                    error=str(exc),
                )

        if count > 0:
            logger.info(
                "parse_results_deleted_for_artifact",
                artifact_id=artifact_id,
                count=count,
            )
        return count

    async def soft_delete_all_by_project(
        self, tenant_id: str, project_id: str
    ) -> int:
        """Soft-delete all active artifacts for a project.

        Returns the number of artifacts that were soft-deleted.
        """
        container = await self._get_container()
        now = datetime.now(UTC)

        query = (
            "SELECT * FROM c "
            "WHERE c.partitionKey = @tenantId AND c.type = 'artifact' "
            "AND c.projectId = @projectId "
            "AND (NOT IS_DEFINED(c.deletedAt) OR IS_NULL(c.deletedAt))"
        )
        params = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@projectId", "value": project_id},
        ]

        count = 0
        async for item in container.query_items(query=query, parameters=params):
            artifact = Artifact.model_validate(item)
            artifact.deleted_at = now
            artifact.updated_at = now
            doc = artifact.model_dump(by_alias=True, mode="json")
            try:
                await container.replace_item(item=artifact.id, body=doc)
                count += 1
            except Exception as exc:
                # Best-effort: log and continue so that a single failing
                # document does not abort deletion of the remaining artifacts.
                logger.warning(
                    "failed_to_soft_delete_artifact",
                    artifact_id=artifact.id,
                    project_id=project_id,
                    error=str(exc),
                )

        logger.info(
            "artifacts_soft_deleted_for_project",
            project_id=project_id,
            count=count,
        )
        return count


artifact_repository = ArtifactRepository()
