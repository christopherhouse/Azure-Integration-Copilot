"""Project CRUD API routes."""

import math
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from shared.models import Meta, PaginatedResponse, PaginationInfo, ResponseEnvelope

from .models import CreateProjectRequest, ProjectResponse, UpdateProjectRequest
from .service import project_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects", tags=["projects"])


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def _get_tenant_id(request: Request) -> str | None:
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        return None
    return tenant.id


@router.post("", status_code=201)
async def create_project(body: CreateProjectRequest, request: Request):
    """Create a new project for the current tenant."""
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

    # Get the user ID from the tenant owner
    tenant = request.state.tenant
    user_id = tenant.owner_id

    project = await project_service.create_project(body, tenant_id, user_id)
    project_resp = ProjectResponse.from_project(project)
    envelope = ResponseEnvelope(
        data=project_resp.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return JSONResponse(status_code=201, content=envelope.model_dump(mode="json"))


@router.get("")
async def list_projects(
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
):
    """List projects for the current tenant (paginated)."""
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

    projects, total_count = await project_service.list_projects(tenant_id, page, page_size)
    total_pages = max(1, math.ceil(total_count / page_size))
    project_responses = [ProjectResponse.from_project(p).model_dump(by_alias=True) for p in projects]

    response = PaginatedResponse(
        data=project_responses,
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


@router.get("/{project_id}")
async def get_project(project_id: str, request: Request):
    """Get a project by ID."""
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

    project = await project_service.get_project(tenant_id, project_id)
    if project is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Project not found.",
                    "request_id": req_id,
                }
            },
        )

    project_resp = ProjectResponse.from_project(project)
    envelope = ResponseEnvelope(
        data=project_resp.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")


@router.patch("/{project_id}")
async def update_project(project_id: str, body: UpdateProjectRequest, request: Request):
    """Update a project's name and/or description."""
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

    project = await project_service.update_project(tenant_id, project_id, body)
    if project is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Project not found.",
                    "request_id": req_id,
                }
            },
        )

    project_resp = ProjectResponse.from_project(project)
    envelope = ResponseEnvelope(
        data=project_resp.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")


@router.delete("/{project_id}", status_code=204)
async def delete_project(project_id: str, request: Request):
    """Soft-delete a project."""
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

    project = await project_service.delete_project(tenant_id, project_id)
    if project is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Project not found.",
                    "request_id": req_id,
                }
            },
        )

    return None
