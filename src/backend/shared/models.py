from datetime import UTC, datetime

from pydantic import BaseModel, Field


class Meta(BaseModel):
    """Metadata included in every API response."""

    request_id: str
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))


class ResponseEnvelope[T](BaseModel):
    """Standard response wrapper for single-object API responses."""

    data: T
    meta: Meta


class PaginationInfo(BaseModel):
    """Pagination metadata for list responses."""

    page: int
    page_size: int
    total_count: int
    total_pages: int
    has_next_page: bool


class PaginatedResponse[T](BaseModel):
    """Standard response wrapper for paginated list API responses."""

    data: list[T]
    meta: Meta
    pagination: PaginationInfo


class ResourceStatus(BaseModel):
    """Status of a downstream dependency checked during health probes."""

    type: str
    available: bool
    latency: str | None = None


class ErrorDetail(BaseModel):
    """Detail of an error in a standard error response."""

    code: str
    message: str
    detail: dict | None = None
    request_id: str | None = None


class ErrorResponse(BaseModel):
    """Standard error response envelope."""

    error: ErrorDetail
