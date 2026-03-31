"""Event type constants and data schemas for CloudEvents published to Event Grid."""

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Event type constants
# ---------------------------------------------------------------------------

EVENT_SOURCE = "/integration-copilot/api"

EVENT_ARTIFACT_UPLOADED = "com.integration-copilot.artifact.uploaded.v1"
EVENT_ARTIFACT_SCAN_PASSED = "com.integration-copilot.artifact.scan-passed.v1"
EVENT_ARTIFACT_SCAN_FAILED = "com.integration-copilot.artifact.scan-failed.v1"
EVENT_ARTIFACT_PARSED = "com.integration-copilot.artifact.parsed.v1"
EVENT_ARTIFACT_PARSE_FAILED = "com.integration-copilot.artifact.parse-failed.v1"
EVENT_GRAPH_UPDATED = "com.integration-copilot.graph.updated.v1"
EVENT_GRAPH_BUILD_FAILED = "com.integration-copilot.graph.build-failed.v1"
EVENT_ANALYSIS_REQUESTED = "com.integration-copilot.analysis.requested.v1"
EVENT_ANALYSIS_COMPLETED = "com.integration-copilot.analysis.completed.v1"
EVENT_ANALYSIS_FAILED = "com.integration-copilot.analysis.failed.v1"

# ---------------------------------------------------------------------------
# Event data schemas
# ---------------------------------------------------------------------------


class ArtifactUploadedData(BaseModel):
    """Data payload for the ArtifactUploaded CloudEvent."""

    tenant_id: str = Field(alias="tenantId")
    project_id: str = Field(alias="projectId")
    artifact_id: str = Field(alias="artifactId")
    artifact_type: str = Field(alias="artifactType")
    blob_path: str = Field(alias="blobPath")
    file_size_bytes: int = Field(alias="fileSizeBytes")
    content_hash: str = Field(alias="contentHash")

    model_config = {"populate_by_name": True}
