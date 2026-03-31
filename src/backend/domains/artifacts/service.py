"""Artifact domain service — business logic for artifact metadata."""

import structlog

from .models import Artifact, ArtifactStatus
from .repository import artifact_repository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class ArtifactService:
    """Manages artifact metadata operations."""

    async def get_artifact(
        self, tenant_id: str, project_id: str, artifact_id: str
    ) -> Artifact | None:
        """Get an artifact by ID, scoped to tenant and project."""
        artifact = await artifact_repository.get_by_id(tenant_id, artifact_id)
        if artifact is None:
            return None
        if artifact.project_id != project_id:
            return None
        if artifact.deleted_at is not None:
            return None
        return artifact

    async def list_artifacts(
        self,
        tenant_id: str,
        project_id: str,
        page: int = 1,
        page_size: int = 20,
        status_filter: ArtifactStatus | None = None,
    ) -> tuple[list[Artifact], int]:
        """List artifacts for a project with pagination and optional status filter."""
        return await artifact_repository.list_by_project(
            tenant_id, project_id, page, page_size, status_filter
        )

    async def delete_artifact(
        self, tenant_id: str, project_id: str, artifact_id: str
    ) -> Artifact | None:
        """Soft-delete an artifact."""
        artifact = await artifact_repository.get_by_id(tenant_id, artifact_id)
        if artifact is None or artifact.project_id != project_id:
            return None
        return await artifact_repository.soft_delete(tenant_id, artifact_id)


artifact_service = ArtifactService()
