"""Realtime API routes — Web PubSub token negotiation."""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from shared.models import Meta, ResponseEnvelope

from .service import realtime_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

router = APIRouter(prefix="/api/v1/realtime", tags=["realtime"])


def _request_id(request: Request) -> str:
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


@router.post("/negotiate")
async def negotiate(request: Request):
    """Generate a Web PubSub client access token for realtime notifications."""
    req_id = _request_id(request)
    tenant = getattr(request.state, "tenant", None)

    if tenant is None:
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

    user_id = getattr(request.state, "user_id", "unknown")
    tenant_id = tenant.id

    token = await realtime_service.generate_client_token(
        user_id=user_id,
        groups=[f"tenant:{tenant_id}"],
    )

    envelope = ResponseEnvelope(
        data=token,
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump(mode="json")
