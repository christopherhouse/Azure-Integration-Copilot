"""Project domain service — business logic for project management."""

import uuid
from datetime import UTC, datetime

import structlog

from .models import CreateProjectRequest, Project, ProjectStatus, UpdateProjectRequest
from .repository import project_repository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ProjectService:
    """Manages project lifecycle operations."""

    async def create_project(
        self, request: CreateProjectRequest, tenant_id: str, user_id: str
    ) -> Project:
        """Create a new project for a tenant."""
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
        return await project_repository.create(project)

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
        """Soft-delete a project."""
        return await project_repository.soft_delete(tenant_id, project_id)


project_service = ProjectService()
