import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

from config import settings
from domains.tenants.router import router as tenant_router
from middleware.auth import AuthMiddleware
from middleware.quota import QuotaMiddleware
from middleware.tenant_context import TenantContextMiddleware
from shared.blob import blob_service
from shared.cosmos import cosmos_service
from shared.events import event_grid_publisher
from shared.exceptions import AppError
from shared.logging import setup_logging, setup_telemetry
from shared.models import ErrorDetail, ErrorResponse, Meta, ResponseEnvelope

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan: startup and shutdown tasks."""
    setup_logging()
    setup_telemetry()
    logger.info("app_started", environment=settings.environment)
    yield
    await cosmos_service.close()
    await blob_service.close()
    await event_grid_publisher.close()
    logger.info("app_stopped")


app = FastAPI(title="Integration Copilot API", version="0.1.0", lifespan=lifespan)

# Instrument FastAPI with OpenTelemetry
FastAPIInstrumentor.instrument_app(app)

# Register middleware (execution order is reversed from registration order in Starlette)
# Desired request flow: auth → tenant_context → quota → handler
# So register in reverse: quota first, then tenant_context, then auth
app.add_middleware(QuotaMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(AuthMiddleware)

# Register routers
app.include_router(tenant_router)



def _request_id(request: Request) -> str:
    """Extract or generate a request ID."""
    return request.headers.get("X-Request-ID", str(uuid.uuid4()))


# ---------------------------------------------------------------------------
# Exception handlers
# ---------------------------------------------------------------------------

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """Convert AppError subclasses into the standard ErrorResponse format."""
    req_id = _request_id(request)
    error_response = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            detail=exc.detail,
            request_id=req_id,
        )
    )
    return JSONResponse(status_code=exc.status_code, content=error_response.model_dump())


@app.exception_handler(404)
async def not_found_handler(request: Request, _exc: Exception) -> JSONResponse:
    """Return standard error format for unknown routes."""
    req_id = _request_id(request)
    error_response = ErrorResponse(
        error=ErrorDetail(
            code="RESOURCE_NOT_FOUND",
            message="The requested resource was not found.",
            request_id=req_id,
        )
    )
    return JSONResponse(status_code=404, content=error_response.model_dump())


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.api_route("/api/v1/health", methods=["GET", "HEAD"])
async def health(request: Request):
    """Liveness probe – always returns 200 when the process is running."""
    req_id = _request_id(request)
    envelope = ResponseEnvelope(
        data={"status": "ok"},
        meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
    )
    return envelope.model_dump()


@app.get("/api/v1/health/ready")
async def health_ready(request: Request):
    """Readiness probe – checks Cosmos DB connectivity."""
    req_id = _request_id(request)

    if not settings.cosmos_db_endpoint:
        # Cosmos DB not configured – return 503 gracefully
        error_response = ErrorResponse(
            error=ErrorDetail(
                code="SERVICE_UNAVAILABLE",
                message="Cosmos DB is not configured.",
                request_id=req_id,
            )
        )
        return JSONResponse(status_code=503, content=error_response.model_dump())

    is_healthy = await cosmos_service.ping()
    if is_healthy:
        envelope = ResponseEnvelope(
            data={"status": "ok"},
            meta=Meta(request_id=req_id, timestamp=datetime.now(UTC)),
        )
        return envelope.model_dump()
    else:
        error_response = ErrorResponse(
            error=ErrorDetail(
                code="SERVICE_UNAVAILABLE",
                message="Cosmos DB is not reachable.",
                request_id=req_id,
            )
        )
        return JSONResponse(status_code=503, content=error_response.model_dump())

