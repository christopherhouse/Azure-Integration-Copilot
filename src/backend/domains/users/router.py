"""User profile API routes."""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from domains.tenants.models import UpdateUserRequest, UserResponse
from domains.tenants.service import user_service
from shared.models import Meta, ResponseEnvelope

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


@router.get("/me")
async def get_current_user(request: Request):
    """Return the current user's profile."""
    req_id = _request_id(request)
    user = getattr(request.state, "user", None)

    if user is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "No user found for the current session.",
                    "request_id": req_id,
                }
            },
        )

    user_resp = UserResponse.from_user(user)
    envelope = ResponseEnvelope(
        data=user_resp.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")


@router.patch("/me")
async def update_current_user(body: UpdateUserRequest, request: Request):
    """Update the current user's profile."""
    req_id = _request_id(request)
    user = getattr(request.state, "user", None)

    if user is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "No user found for the current session.",
                    "request_id": req_id,
                }
            },
        )

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

    updated = await user_service.update_user_gravatar_email(
        user_id=user.id,
        tenant_id=tenant.id,
        gravatar_email=body.gravatar_email,
    )
    if updated is None:
        return JSONResponse(
            status_code=404,
            content={
                "error": {
                    "code": "RESOURCE_NOT_FOUND",
                    "message": "User not found.",
                    "request_id": req_id,
                }
            },
        )

    user_resp = UserResponse.from_user(updated)
    envelope = ResponseEnvelope(
        data=user_resp.model_dump(by_alias=True),
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")
