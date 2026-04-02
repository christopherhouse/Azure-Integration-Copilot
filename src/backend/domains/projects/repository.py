"""Cosmos DB repository for project documents."""

from datetime import UTC, datetime

import structlog
from azure.core import MatchConditions
from azure.cosmos import exceptions as cosmos_exceptions
from azure.cosmos.aio import ContainerProxy

from shared.cosmos import cosmos_service

from .models import Project, ProjectStatus

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DATABASE_NAME = "integration-copilot"
CONTAINER_NAME = "projects"


class ProjectRepository:
    """Cosmos DB operations for the projects container (project documents)."""

    async def _get_container(self) -> ContainerProxy:
        return await cosmos_service.get_container(DATABASE_NAME, CONTAINER_NAME)

    async def create(self, project: Project) -> Project:
        """Create a new project document."""
        container = await self._get_container()
        doc = project.model_dump(by_alias=True, mode="json")
        result = await container.create_item(body=doc)
        logger.info("project_created", project_id=project.id, tenant_id=project.tenant_id)
        return Project.model_validate(result)

    async def get_by_id(self, tenant_id: str, project_id: str) -> Project | None:
        """Get a project by ID, scoped to tenant."""
        container = await self._get_container()
        try:
            doc = await container.read_item(item=project_id, partition_key=tenant_id)
            if doc.get("type") != "project":
                return None
            project = Project.model_validate(doc)
            project.etag = doc.get("_etag")
            return project
        except cosmos_exceptions.CosmosResourceNotFoundError:
            return None

    async def list_by_tenant(
        self, tenant_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Project], int]:
        """List projects for a tenant (paginated, excluding deleted)."""
        container = await self._get_container()

        # Count query
        count_query = (
            "SELECT VALUE COUNT(1) FROM c "
            "WHERE c.partitionKey = @tenantId AND c.type = 'project' AND c.status != 'deleted'"
        )
        count_params = [{"name": "@tenantId", "value": tenant_id}]
        total_count = 0
        async for item in container.query_items(query=count_query, parameters=count_params):
            total_count = item

        # Data query with OFFSET/LIMIT
        offset = (page - 1) * page_size
        data_query = (
            "SELECT * FROM c "
            "WHERE c.partitionKey = @tenantId AND c.type = 'project' AND c.status != 'deleted' "
            "ORDER BY c.createdAt DESC "
            "OFFSET @offset LIMIT @limit"
        )
        data_params = [
            {"name": "@tenantId", "value": tenant_id},
            {"name": "@offset", "value": offset},
            {"name": "@limit", "value": page_size},
        ]
        projects: list[Project] = []
        async for item in container.query_items(query=data_query, parameters=data_params):
            projects.append(Project.model_validate(item))

        return projects, total_count

    async def update(self, project: Project) -> Project:
        """Update an existing project document with ETag-based optimistic concurrency."""
        container = await self._get_container()
        project.updated_at = datetime.now(UTC)
        doc = project.model_dump(by_alias=True, mode="json")

        kwargs: dict = {}
        if project.etag:
            kwargs["etag"] = project.etag
            kwargs["match_condition"] = MatchConditions.IfNotModified

        result = await container.replace_item(item=project.id, body=doc, **kwargs)
        logger.info("project_updated", project_id=project.id)
        updated = Project.model_validate(result)
        updated.etag = result.get("_etag")
        return updated

    async def soft_delete(self, tenant_id: str, project_id: str) -> Project | None:
        """Soft-delete a project by setting status to deleted."""
        project = await self.get_by_id(tenant_id, project_id)
        if project is None:
            return None
        project.status = ProjectStatus.DELETED
        project.deleted_at = datetime.now(UTC)
        return await self.update(project)


project_repository = ProjectRepository()
