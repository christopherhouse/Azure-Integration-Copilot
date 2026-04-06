"""Analysis domain models — Pydantic models for analysis documents and API."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class AnalysisStatus(StrEnum):
    """Status of an analysis request."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"


class EvaluationVerdict(StrEnum):
    """Verdict from the quality evaluator agent."""

    PASSED = "PASSED"
    FAILED = "FAILED"


class EvaluationResult(BaseModel):
    """Result from the quality evaluator agent."""

    verdict: EvaluationVerdict
    confidence: float = 0.0
    issues: list[str] = Field(default_factory=list)
    summary: str = ""


class ToolCallRecord(BaseModel):
    """Record of a tool call made during analysis."""

    tool_name: str = Field(alias="toolName")
    arguments: dict = Field(default_factory=dict)
    output: dict | str | None = None

    model_config = {"populate_by_name": True}


class AnalysisResult(BaseModel):
    """Result of an analysis, including agent response and evaluation."""

    response: str = ""
    tool_calls: list[ToolCallRecord] = Field(default_factory=list, alias="toolCalls")
    evaluation: EvaluationResult | None = None
    retry_count: int = Field(default=0, alias="retryCount")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Cosmos DB document model
# ---------------------------------------------------------------------------


class Analysis(BaseModel):
    """Analysis document stored in the ``analyses`` Cosmos DB container."""

    id: str
    partition_key: str = Field(alias="partitionKey")
    type: str = "analysis"
    tenant_id: str = Field(alias="tenantId")
    project_id: str = Field(alias="projectId")
    prompt: str
    status: AnalysisStatus = AnalysisStatus.PENDING
    result: AnalysisResult | None = None
    error: str | None = None
    requested_by: str = Field(default="", alias="requestedBy")
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")
    completed_at: datetime | None = Field(default=None, alias="completedAt")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# API request/response models
# ---------------------------------------------------------------------------


class CreateAnalysisRequest(BaseModel):
    """Request body for creating a new analysis."""

    prompt: str = Field(..., min_length=1, max_length=2000)


class AnalysisResponse(BaseModel):
    """Analysis data returned in API responses."""

    id: str
    project_id: str = Field(alias="projectId")
    prompt: str
    status: AnalysisStatus
    result: AnalysisResult | None = None
    error: str | None = None
    requested_by: str = Field(alias="requestedBy")
    created_at: datetime = Field(alias="createdAt")
    completed_at: datetime | None = Field(alias="completedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_analysis(cls, analysis: Analysis) -> AnalysisResponse:
        """Build a response from an Analysis domain model."""
        return cls(
            id=analysis.id,
            projectId=analysis.project_id,
            prompt=analysis.prompt,
            status=analysis.status,
            result=analysis.result,
            error=analysis.error,
            requestedBy=analysis.requested_by,
            createdAt=analysis.created_at,
            completedAt=analysis.completed_at,
        )
