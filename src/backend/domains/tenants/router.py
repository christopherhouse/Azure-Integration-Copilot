"""Tenant CRUD API routes."""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from shared.models import Meta, ResponseEnvelope

from .models import CreateTenantRequest, TenantResponse, UpdateTenantRequest
from .service import tenant_service, user_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/tenants", tags=["tenants"])


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


@router.post("", status_code=201)
async def create_tenant(body: CreateTenantRequest, request: Request):
    """Register a new tenant and owner user."""
    req_id = _request_id(request)
    external_id = getattr(request.state, "external_id", "")

    # Check if user already has a tenant
    existing_user = await user_service.get_user_by_external_id(external_id)
    if existing_user is not None:
        return JSONResponse(
            status_code=409,
            content={
                "error": {
                    "code": "CONFLICT",
                    "message": "User already has a tenant.",
                    "request_id": req_id,
                }
            },
        )

    tenant, _user = await tenant_service.create_tenant(body, external_id)
    tenant_resp = TenantResponse.from_tenant(tenant)
    envelope = ResponseEnvelope(
        data=tenant_resp.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return JSONResponse(status_code=201, content=envelope.model_dump(mode="json"))


@router.get("/me")
async def get_current_tenant(request: Request):
    """Return the current user's tenant with usage data."""
    req_id = _request_id(request)
    tenant = getattr(request.state, "tenant", None)

    if tenant is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "No tenant found for the current user.",
                    "request_id": req_id,
                }
            },
        )

    tenant_resp = TenantResponse.from_tenant(tenant)
    envelope = ResponseEnvelope(
        data=tenant_resp.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")


@router.patch("/me")
async def update_current_tenant(body: UpdateTenantRequest, request: Request):
    """Update the current tenant's display name."""
    req_id = _request_id(request)
    tenant = getattr(request.state, "tenant", None)

    if tenant is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "No tenant found for the current user.",
                    "request_id": req_id,
                }
            },
        )

    if body.display_name is not None:
        updated = await tenant_service.update_tenant_display_name(tenant.id, body.display_name)
        if updated is None:
            return JSONResponse(
                status_code=404,
                content={
                    "error": {
                        "code": "RESOURCE_NOT_FOUND",
                        "message": "Tenant not found.",
                        "request_id": req_id,
                    }
                },
            )
        tenant = updated

    tenant_resp = TenantResponse.from_tenant(tenant)
    envelope = ResponseEnvelope(
        data=tenant_resp.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")
