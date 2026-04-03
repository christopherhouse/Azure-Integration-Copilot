"""Graph query API routes."""

import math
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse

from shared.models import Meta, PaginatedResponse, PaginationInfo, ResponseEnvelope

from .service import graph_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/graph", tags=["graph"])


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def _get_tenant_id(request: Request) -> str | None:
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        return None
    return tenant.id


def _unauthorized_response(req_id: str) -> JSONResponse:
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


@router.get("/summary")
async def get_graph_summary(project_id: str, request: Request):
    """Get graph summary with component/edge counts."""
    req_id = _request_id(request)
    tenant_id = _get_tenant_id(request)

    if tenant_id is None:
        return _unauthorized_response(req_id)

    summary = await graph_service.get_summary(tenant_id, project_id)
    if summary is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Graph summary not found. No graph has been built for this project yet.",
                    "request_id": req_id,
                }
            },
        )

    envelope = ResponseEnvelope(
        data=summary.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")


@router.get("/components")
async def list_components(
    project_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    component_type: str | None = Query(default=None, alias="componentType"),
):
    """List components for a project (paginated, filterable by type)."""
    req_id = _request_id(request)
    tenant_id = _get_tenant_id(request)

    if tenant_id is None:
        return _unauthorized_response(req_id)

    components, total_count = await graph_service.list_components(
        tenant_id, project_id, page, page_size, component_type
    )
    total_pages = max(1, math.ceil(total_count / page_size))
    component_dicts = [c.model_dump(by_alias=True) for c in components]

    response = PaginatedResponse(
        data=component_dicts,
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


@router.get("/components/{component_id}")
async def get_component(project_id: str, component_id: str, request: Request):
    """Get a component by ID."""
    req_id = _request_id(request)
    tenant_id = _get_tenant_id(request)

    if tenant_id is None:
        return _unauthorized_response(req_id)

    component = await graph_service.get_component(tenant_id, project_id, component_id)
    if component is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Component not found.",
                    "detail": {"resourceType": "component", "resourceId": component_id},
                    "request_id": req_id,
                }
            },
        )

    envelope = ResponseEnvelope(
        data=component.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")


@router.get("/components/{component_id}/neighbors")
async def get_neighbors(
    project_id: str,
    component_id: str,
    request: Request,
    direction: str = Query(default="both", pattern="^(both|incoming|outgoing)$"),
):
    """Get incoming/outgoing neighbors of a component."""
    req_id = _request_id(request)
    tenant_id = _get_tenant_id(request)

    if tenant_id is None:
        return _unauthorized_response(req_id)

    neighbors = await graph_service.get_neighbors(
        tenant_id, project_id, component_id, direction
    )

    envelope = ResponseEnvelope(
        data=[n.model_dump(by_alias=True) for n in neighbors],
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")


@router.get("/edges")
async def list_edges(
    project_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
):
    """List edges for a project (paginated)."""
    req_id = _request_id(request)
    tenant_id = _get_tenant_id(request)

    if tenant_id is None:
        return _unauthorized_response(req_id)

    edges, total_count = await graph_service.list_edges(
        tenant_id, project_id, page, page_size
    )
    total_pages = max(1, math.ceil(total_count / page_size))
    edge_dicts = [e.model_dump(by_alias=True) for e in edges]

    response = PaginatedResponse(
        data=edge_dicts,
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
