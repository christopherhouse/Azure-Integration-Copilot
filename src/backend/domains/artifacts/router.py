"""Artifact metadata API routes."""

import math
import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, File, Form, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response

from shared.models import Meta, PaginatedResponse, PaginationInfo, ResponseEnvelope

from .models import ArtifactResponse, ArtifactStatus
from .service import artifact_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/projects/{project_id}/artifacts", tags=["artifacts"])


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


def _get_tenant(request: Request):
    """Return (tenant, tier) or (None, None) from request state."""
    tenant = getattr(request.state, "tenant", None)
    tier = getattr(request.state, "tier", None)
    return tenant, tier


def _get_tenant_id(request: Request) -> str | None:
    tenant = getattr(request.state, "tenant", None)
    if tenant is None:
        return None
    return tenant.id


# ---------------------------------------------------------------------------
# POST — Upload artifact
# ---------------------------------------------------------------------------


@router.post("", status_code=202)
async def upload_artifact(
    project_id: str,
    request: Request,
    file: UploadFile = File(...),  # noqa: B008
    artifact_type: str | None = Form(default=None),  # noqa: B008
):
    """Upload an artifact file (multipart/form-data)."""
    req_id = _request_id(request)
    tenant, tier = _get_tenant(request)

    if tenant is None or tier is None:
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

    try:
        artifact = await artifact_service.upload_artifact(
            tenant=tenant,
            tier=tier,
            project_id=project_id,
            file=file,
            artifact_type_override=artifact_type,
        )
    except ValueError as exc:
        logger.warning(
            "File upload rejected due to ValueError",
            request_id=req_id,
            tenant_id=_get_tenant_id(request),
            project_id=project_id,
            error=str(exc),
        )
        return JSONResponse(
            status_code=413,
            content={
                "error": {
                    "code": "FILE_TOO_LARGE",
                    "message": "Uploaded file is too large.",
                    "request_id": req_id,
                }
            },
        )

    artifact_resp = ArtifactResponse.from_artifact(artifact)
    envelope = ResponseEnvelope(
        data=artifact_resp.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return JSONResponse(
        status_code=202,
        content=envelope.model_dump(mode="json"),
    )


# ---------------------------------------------------------------------------
# GET — List artifacts
# ---------------------------------------------------------------------------


@router.get("")
async def list_artifacts(
    project_id: str,
    request: Request,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100, alias="pageSize"),
    status: ArtifactStatus | None = Query(default=None),  # noqa: B008
):
    """List artifacts for a project (paginated, optionally filtered by status)."""
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

    artifacts, total_count = await artifact_service.list_artifacts(
        tenant_id, project_id, page, page_size, status
    )
    total_pages = max(1, math.ceil(total_count / page_size))
    artifact_responses = [ArtifactResponse.from_artifact(a).model_dump(by_alias=True) for a in artifacts]

    response = PaginatedResponse(
        data=artifact_responses,
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


@router.get("/{artifact_id}")
async def get_artifact(project_id: str, artifact_id: str, request: Request):
    """Get artifact metadata by ID."""
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

    artifact = await artifact_service.get_artifact(tenant_id, project_id, artifact_id)
    if artifact is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Artifact not found.",
                    "request_id": req_id,
                }
            },
        )

    artifact_resp = ArtifactResponse.from_artifact(artifact)
    envelope = ResponseEnvelope(
        data=artifact_resp.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")


@router.delete("/{artifact_id}", status_code=204)
async def delete_artifact(project_id: str, artifact_id: str, request: Request):
    """Soft-delete an artifact."""
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

    artifact = await artifact_service.delete_artifact(tenant_id, project_id, artifact_id)
    if artifact is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Artifact not found.",
                    "request_id": req_id,
                }
            },
        )

    return None


# ---------------------------------------------------------------------------
# GET — Download artifact file
# ---------------------------------------------------------------------------


@router.get("/{artifact_id}/download")
async def download_artifact(project_id: str, artifact_id: str, request: Request):
    """Download the raw artifact file from Blob Storage."""
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

    result = await artifact_service.download_artifact(tenant_id, project_id, artifact_id)
    if result is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "Artifact not found.",
                    "request_id": req_id,
                }
            },
        )

    content, filename = result
    return Response(
        content=content,
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
