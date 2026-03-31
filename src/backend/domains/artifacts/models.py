"""Artifact domain models and status state machine."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field

from shared.exceptions import AppError


class InvalidStatusTransition(AppError):
    """Raised when an artifact status transition is not allowed."""

    def __init__(self, current: str, target: str) -> None:
        super().__init__(
            status_code=409,
            code="INVALID_STATUS_TRANSITION",
            message=f"Cannot transition from '{current}' to '{target}'.",
            detail={"current": current, "target": target},
        )


class ArtifactStatus(StrEnum):
    """Artifact lifecycle status."""

    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    SCANNING = "scanning"
    SCAN_PASSED = "scan_passed"
    SCAN_FAILED = "scan_failed"
    PARSING = "parsing"
    PARSED = "parsed"
    PARSE_FAILED = "parse_failed"
    GRAPH_BUILDING = "graph_building"
    GRAPH_BUILT = "graph_built"
    GRAPH_FAILED = "graph_failed"
    UNSUPPORTED = "unsupported"


VALID_TRANSITIONS: dict[ArtifactStatus, set[ArtifactStatus]] = {
    ArtifactStatus.UPLOADING: {ArtifactStatus.UPLOADED, ArtifactStatus.UNSUPPORTED},
    ArtifactStatus.UPLOADED: {ArtifactStatus.SCANNING},
    ArtifactStatus.SCANNING: {ArtifactStatus.SCAN_PASSED, ArtifactStatus.SCAN_FAILED},
    ArtifactStatus.SCAN_PASSED: {ArtifactStatus.PARSING},
    ArtifactStatus.PARSING: {ArtifactStatus.PARSED, ArtifactStatus.PARSE_FAILED},
    ArtifactStatus.PARSED: {ArtifactStatus.GRAPH_BUILDING},
    ArtifactStatus.GRAPH_BUILDING: {ArtifactStatus.GRAPH_BUILT, ArtifactStatus.GRAPH_FAILED},
}


def transition_status(current: ArtifactStatus, target: ArtifactStatus) -> ArtifactStatus:
    """Validate and perform a status transition.

    Raises InvalidStatusTransition if the transition is not allowed.
    """
    valid = VALID_TRANSITIONS.get(current, set())
    if target not in valid:
        raise InvalidStatusTransition(current=current, target=target)
    return target


class ArtifactError(BaseModel):
    """Error information for a failed artifact."""

    code: str
    message: str
    occurred_at: datetime = Field(alias="occurredAt")

    model_config = {"populate_by_name": True}


class Artifact(BaseModel):
    """Artifact document stored in Cosmos DB."""

    id: str
    partition_key: str = Field(alias="partitionKey")
    type: str = "artifact"
    tenant_id: str = Field(alias="tenantId")
    project_id: str = Field(alias="projectId")
    name: str
    artifact_type: str | None = Field(default=None, alias="artifactType")
    status: ArtifactStatus = ArtifactStatus.UPLOADING
    file_size_bytes: int | None = Field(default=None, alias="fileSizeBytes")
    blob_path: str | None = Field(default=None, alias="blobPath")
    content_hash: str | None = Field(default=None, alias="contentHash")
    error: ArtifactError | None = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="updatedAt")
    deleted_at: datetime | None = Field(default=None, alias="deletedAt")
    etag: str | None = Field(default=None, alias="_etag", exclude=True)

    model_config = {"populate_by_name": True}


class ArtifactResponse(BaseModel):
    """Artifact data returned in API responses."""

    id: str
    name: str
    artifact_type: str | None = Field(alias="artifactType")
    status: ArtifactStatus
    file_size_bytes: int | None = Field(alias="fileSizeBytes")
    content_hash: str | None = Field(alias="contentHash")
    error: ArtifactError | None = None
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_artifact(cls, artifact: Artifact) -> "ArtifactResponse":
        """Build a response from an Artifact domain model."""
        return cls(
            id=artifact.id,
            name=artifact.name,
            artifactType=artifact.artifact_type,
            status=artifact.status,
            fileSizeBytes=artifact.file_size_bytes,
            contentHash=artifact.content_hash,
            error=artifact.error,
            createdAt=artifact.created_at,
            updatedAt=artifact.updated_at,
        )
