"""Analysis API routes."""

import math
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from shared.events import event_grid_publisher
from shared.models import Meta, PaginatedResponse, PaginationInfo, ResponseEnvelope

from .models import AnalysisResponse, CreateAnalysisRequest
from .repository import analysis_repository
from .service import AnalysisService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/analyses", tags=["analyses"])

analysis_service = AnalysisService(
    repository=analysis_repository,
    event_publisher=event_grid_publisher,
)


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def _get_tenant_id(request: Request) -> str | None:
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        return None
    return tenant.id


def _get_user_id(request: Request) -> str:
    return getattr(request.state, "user_id", "unknown")


# ---------------------------------------------------------------------------
# POST — Create analysis
# ---------------------------------------------------------------------------


@router.post("", status_code=202)
async def create_analysis(
    project_id: str,
    body: CreateAnalysisRequest,
    request: Request,
):
    """Request a new AI analysis of the project's integration landscape."""
    req_id = _request_id(request)
    tenant_id = _get_tenant_id(request)

    if tenant_id is None:
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Tenant context required.",
                    "request_id": req_id,
                }
            },
        )

    user_id = _get_user_id(request)

    analysis = await analysis_service.create_analysis(
        tenant_id=tenant_id,
        project_id=project_id,
        prompt=body.prompt,
        requested_by=user_id,
    )

    analysis_resp = AnalysisResponse.from_analysis(analysis)
    envelope = ResponseEnvelope(
        data=analysis_resp.model_dump(by_alias=True, mode="json"),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return JSONResponse(
        status_code=202,
        content=envelope.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# GET — List analyses
# ---------------------------------------------------------------------------


@router.get("")
async def list_analyses(
    project_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
):
    """List analyses for a project (paginated, newest first)."""
    req_id = _request_id(request)
    tenant_id = _get_tenant_id(request)

    if tenant_id is None:
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Tenant context required.",
                    "request_id": req_id,
                }
            },
        )

    analyses, total_count = await analysis_service.list_analyses(
        tenant_id, project_id, page, page_size
    )
    total_pages = max(1, math.ceil(total_count / page_size))
    analysis_responses = [
        AnalysisResponse.from_analysis(a).model_dump(by_alias=True, mode="json")
        for a in analyses
    ]

    response = PaginatedResponse(
        data=analysis_responses,
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
        pagination=PaginationInfo(
            page=page,
            page_size=page_size,
            total_count=total_count,
            total_pages=total_pages,
            has_next_page=page < total_pages,
        ),
    )
    return response.model_dump(mode="json")


# ---------------------------------------------------------------------------
# GET — Get analysis by ID
# ---------------------------------------------------------------------------


@router.get("/{analysis_id}")
async def get_analysis(
    project_id: str,
    analysis_id: str,
    request: Request,
):
    """Get a single analysis result."""
    req_id = _request_id(request)
    tenant_id = _get_tenant_id(request)

    if tenant_id is None:
        return JSONResponse(
            status_code=401,
            content={
                "error": {
                    "code": "UNAUTHORIZED",
                    "message": "Tenant context required.",
                    "request_id": req_id,
                }
            },
        )

    analysis = await analysis_service.get_analysis(tenant_id, project_id, analysis_id)
    if analysis is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Analysis not found.",
                    "request_id": req_id,
                }
            },
        )

    analysis_resp = AnalysisResponse.from_analysis(analysis)
    envelope = ResponseEnvelope(
        data=analysis_resp.model_dump(by_alias=True, mode="json"),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")
