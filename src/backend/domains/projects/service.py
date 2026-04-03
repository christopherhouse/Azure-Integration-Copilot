"""Project domain service — business logic for project management."""

import uuid
from datetime import UTC, datetime

import structlog

from domains.artifacts.repository import artifact_repository
from domains.graph.repository import graph_repository
from domains.tenants.repository import tenant_repository
from domains.tenants.service import tier_service
from shared.exceptions import QuotaExceededError

from .models import CreateProjectRequest, Project, ProjectStatus, UpdateProjectRequest
from .repository import project_repository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ProjectService:
    """Manages project lifecycle operations."""

    async def create_project(
        self, request: CreateProjectRequest, tenant_id: str, user_id: str
    ) -> Project:
        """Create a new project for a tenant.

        Uses an increment-first reservation pattern:
        1. Increment the usage counter (reserves a slot).
        2. Verify the new count does not exceed the tier limit.
        3. Create the project document.
        If step 2 or 3 fails the reservation is rolled back.
        """
        # Step 1 — reserve a slot by incrementing the counter first.
        updated_tenant = await tenant_repository.increment_usage(
            tenant_id, "project_count"
        )
        if updated_tenant is None:
            raise QuotaExceededError(
                message="Tenant not found.",
                detail={"limit": "max_projects"},
            )

        # Step 2 — verify the new count is within limits.
        tier = tier_service.get_tier(updated_tenant.tier_id)
        if updated_tenant.usage.project_count > tier.limits.max_projects:
            # Over limit — release the reservation.
            await tenant_repository.increment_usage(
                tenant_id, "project_count", amount=-1
            )
            # Report the pre-increment count (subtract the +1 reservation) so
            # the client sees how many projects the tenant actually has.
            raise QuotaExceededError(
                message="Quota exceeded for max_projects.",
                detail={
                    "limit": "max_projects",
                    "current": updated_tenant.usage.project_count - 1,
                    "max": tier.limits.max_projects,
                },
            )

        # Step 3 — create the project document.
        project_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        project = Project(
            id=project_id,
            partitionKey=tenant_id,
            tenantId=tenant_id,
            name=request.name,
            description=request.description,
            createdBy=user_id,
            createdAt=now,
            updatedAt=now,
        )
        try:
            return await project_repository.create(project)
        except Exception:
            # Roll back the reservation on creation failure.
            await tenant_repository.increment_usage(
                tenant_id, "project_count", amount=-1
            )
            raise

    async def get_project(self, tenant_id: str, project_id: str) -> Project | None:
        """Get a project by ID, scoped to tenant. Returns None for deleted projects."""
        project = await project_repository.get_by_id(tenant_id, project_id)
        if project is not None and project.status == ProjectStatus.DELETED:
            return None
        return project

    async def list_projects(
        self, tenant_id: str, page: int = 1, page_size: int = 20
    ) -> tuple[list[Project], int]:
        """List projects for a tenant with pagination."""
        return await project_repository.list_by_tenant(tenant_id, page, page_size)

    async def update_project(
        self, tenant_id: str, project_id: str, request: UpdateProjectRequest
    ) -> Project | None:
        """Update a project's name and/or description."""
        project = await project_repository.get_by_id(tenant_id, project_id)
        if project is None or project.status == ProjectStatus.DELETED:
            return None

        if request.name is not None:
            project.name = request.name
        if request.description is not None:
            project.description = request.description

        return await project_repository.update(project)

    async def delete_project(self, tenant_id: str, project_id: str) -> Project | None:
        """Soft-delete a project and cascade-delete related artifacts and graph data.

        Returns the deleted project, or None if the project does not exist or
        has already been deleted.  Usage counters are only adjusted the first
        time a project is deleted; duplicate calls are safely ignored.
        """
        project = await project_repository.get_by_id(tenant_id, project_id)
        if project is None or project.status == ProjectStatus.DELETED:
            return None

        # Cascade: soft-delete all active artifacts and adjust usage counters.
        deleted_artifact_count = await artifact_repository.soft_delete_all_by_project(
            tenant_id, project_id
        )
        if deleted_artifact_count > 0:
            await tenant_repository.increment_usage(
                tenant_id, "total_artifact_count", amount=-deleted_artifact_count
            )

        # Cascade: hard-delete all graph data for this project.
        graph_partition_key = f"{tenant_id}:{project_id}"
        await graph_repository.delete_all_by_project(graph_partition_key)

        # Soft-delete the project itself and decrement the tenant project quota.
        deleted = await project_repository.soft_delete(tenant_id, project_id)
        if deleted is not None:
            await tenant_repository.increment_usage(tenant_id, "project_count", amount=-1)
        return deleted


project_service = ProjectService()
