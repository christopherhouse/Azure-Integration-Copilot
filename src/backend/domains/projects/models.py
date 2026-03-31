"""Project domain models."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class ProjectStatus(StrEnum):
    """Project lifecycle status."""

    ACTIVE = "active"
    ARCHIVED = "archived"
    DELETED = "deleted"


class Project(BaseModel):
    """Project document stored in Cosmos DB."""

    id: str
    partition_key: str = Field(alias="partitionKey")
    type: str = "project"
    tenant_id: str = Field(alias="tenantId")
    name: str
    description: str | None = None
    status: ProjectStatus = ProjectStatus.ACTIVE
    artifact_count: int = Field(default=0, alias="artifactCount")
    graph_version: int = Field(default=0, alias="graphVersion")
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="updatedAt")
    deleted_at: datetime | None = Field(default=None, alias="deletedAt")
    etag: str | None = Field(default=None, alias="_etag", exclude=True)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateProjectRequest(BaseModel):
    """Request body for creating a new project."""

    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class UpdateProjectRequest(BaseModel):
    """Request body for updating a project."""

    name: str | None = Field(default=None, min_length=1, max_length=100)
    description: str | None = Field(default=None, max_length=500)


class ProjectResponse(BaseModel):
    """Project data returned in API responses."""

    id: str
    name: str
    description: str | None
    status: ProjectStatus
    artifact_count: int = Field(alias="artifactCount")
    graph_version: int = Field(alias="graphVersion")
    created_by: str = Field(alias="createdBy")
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_project(cls, project: Project) -> "ProjectResponse":
        """Build a response from a Project domain model."""
        return cls(
            id=project.id,
            name=project.name,
            description=project.description,
            status=project.status,
            artifactCount=project.artifact_count,
            graphVersion=project.graph_version,
            createdBy=project.created_by,
            createdAt=project.created_at,
            updatedAt=project.updated_at,
        )
