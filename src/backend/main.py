import asyncio
import time
import uuid
from contextlib import asynccontextmanager
from datetime import UTC, datetime

import structlog
from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from opentelemetry import trace
from opentelemetry.trace import StatusCode

from config import settings
from domains.artifacts.router import router as artifact_router
from domains.projects.router import router as project_router
from domains.tenants.router import router as tenant_router
from domains.users.router import router as user_router
from middleware.auth import AuthMiddleware
from middleware.quota import QuotaMiddleware
from middleware.tenant_context import TenantContextMiddleware
from shared.blob import blob_service
from shared.cosmos import cosmos_service
from shared.events import event_grid_publisher
from shared.exceptions import AppError
from shared.logging import setup_logging, setup_telemetry
from shared.models import ErrorDetail, ErrorResponse, Meta, ResourceStatus, ResponseEnvelope
from shared.webpubsub import web_pubsub_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI):
    """Application lifespan: startup and shutdown tasks."""
    logger.info("app_started", environment=settings.environment)
    yield
    await cosmos_service.close()
    await blob_service.close()
    await event_grid_publisher.close()
    await web_pubsub_service.close()
    logger.info("app_stopped")


app = FastAPI(title="Integrisight.ai API", version="0.1.0", lifespan=lifespan)

# Register middleware (execution order is reversed from registration order in Starlette)
# Desired request flow: cors → auth → tenant_context → quota → handler
# So register in reverse: quota first, then tenant_context, then auth, then cors
app.add_middleware(QuotaMiddleware)
app.add_middleware(TenantContextMiddleware)
app.add_middleware(AuthMiddleware)

# CORS must be outermost so preflight OPTIONS requests are handled before auth.
# Starlette reverses registration order, so register CORS last.
if settings.cors_allowed_origins:
    cors_origins = [o.strip() for o in settings.cors_allowed_origins.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "X-Request-ID"],
        allow_credentials=True,
    )

# ---------------------------------------------------------------------------
# Logging & telemetry — must be initialised at module level
# ---------------------------------------------------------------------------
# Starlette builds the middleware stack on the first ASGI scope (the lifespan
# startup event).  ``setup_telemetry`` calls ``instrument_app`` which replaces
# ``build_middleware_stack`` — so it must run *before* the first ASGI scope
# arrives.  Module-level initialisation guarantees this.
setup_logging()
setup_telemetry(app)

# Register routers
app.include_router(tenant_router)
app.include_router(user_router)
app.include_router(project_router)
app.include_router(artifact_router)



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

    # Record server-side errors on the active span so they appear in Azure Monitor
    # as failed operations. Client errors (4xx) are expected outcomes and are not
    # marked as span errors to avoid inflating the error rate.
    if exc.status_code >= 500:
        span = trace.get_current_span()
        span.record_exception(exc)
        span.set_status(StatusCode.ERROR, exc.message)

    error_response = ErrorResponse(
        error=ErrorDetail(
            code=exc.code,
            message=exc.message,
            detail=exc.detail,
            request_id=req_id,
        )
    )
    return JSONResponse(status_code=exc.status_code, content=error_response.model_dump())


@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Catch-all handler for unexpected exceptions.

    Records the exception on the active OpenTelemetry span so that it appears
    in Azure Monitor Application Insights as a failed operation with full
    stack-trace details.
    """
    req_id = _request_id(request)
    span = trace.get_current_span()
    span.record_exception(exc)
    span.set_status(StatusCode.ERROR, str(exc))
    logger.exception("unhandled_exception", request_id=req_id, path=request.url.path)
    error_response = ErrorResponse(
        error=ErrorDetail(
            code="INTERNAL_SERVER_ERROR",
            message="An unexpected error occurred.",
            request_id=req_id,
        )
    )
    return JSONResponse(status_code=500, content=error_response.model_dump())


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
# Dependency health checks
# ---------------------------------------------------------------------------

async def _check_database() -> ResourceStatus:
    """Check Cosmos DB connectivity and measure latency."""
    if not settings.cosmos_db_endpoint:
        return ResourceStatus(type="database", available=False)
    start_time = time.perf_counter()
    available = await cosmos_service.ping()
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    if available:
        return ResourceStatus(
            type="database", available=True, latency=f"{elapsed_ms:.1f} ms"
        )
    return ResourceStatus(type="database", available=False)


async def _check_object_storage() -> ResourceStatus:
    """Check Azure Blob Storage connectivity and measure latency."""
    if not settings.blob_storage_endpoint:
        return ResourceStatus(type="object_storage", available=False)
    start_time = time.perf_counter()
    available = await blob_service.ping()
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    if available:
        return ResourceStatus(
            type="object_storage", available=True, latency=f"{elapsed_ms:.1f} ms"
        )
    return ResourceStatus(type="object_storage", available=False)


async def _check_broker() -> ResourceStatus:
    """Check Azure Event Grid Namespace connectivity and measure latency."""
    if not settings.event_grid_namespace_endpoint:
        return ResourceStatus(type="broker", available=False)
    start_time = time.perf_counter()
    available = await event_grid_publisher.ping()
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    if available:
        return ResourceStatus(
            type="broker", available=True, latency=f"{elapsed_ms:.1f} ms"
        )
    return ResourceStatus(type="broker", available=False)


async def _check_messaging() -> ResourceStatus:
    """Check Azure Web PubSub connectivity and measure latency."""
    if not settings.web_pubsub_endpoint:
        return ResourceStatus(type="messaging", available=False)
    start_time = time.perf_counter()
    available = await web_pubsub_service.ping()
    elapsed_ms = (time.perf_counter() - start_time) * 1000
    if available:
        return ResourceStatus(
            type="messaging", available=True, latency=f"{elapsed_ms:.1f} ms"
        )
    return ResourceStatus(type="messaging", available=False)


async def _check_all_resources() -> tuple[list[ResourceStatus], str]:
    """Run all dependency checks in parallel.

    Returns a tuple of (resource_statuses, aggregate_duration) where
    aggregate_duration is the wall-clock time of the parallel execution
    formatted as ``"<value> ms"``.
    """
    start = time.perf_counter()
    results = await asyncio.gather(
        _check_database(),
        _check_object_storage(),
        _check_broker(),
        _check_messaging(),
    )
    elapsed_ms = (time.perf_counter() - start) * 1000
    return list(results), f"{elapsed_ms:.1f} ms"


def _compute_health_status(resources: list[ResourceStatus]) -> str:
    """Compute overall health status from resource availability.

    Returns:
        "ok"       – all dependencies available
        "degraded" – one or more but not all dependencies failed
        "failed"   – all dependencies failed
    """
    if not resources:
        return "failed"
    available_count = sum(1 for r in resources if r.available)
    if available_count == len(resources):
        return "ok"
    if available_count == 0:
        return "failed"
    return "degraded"


# ---------------------------------------------------------------------------
# Health endpoints
# ---------------------------------------------------------------------------

@app.api_route("/api/v1/health", methods=["GET", "HEAD"])
async def health(request: Request):
    """Health probe – checks downstream dependencies and returns their status.

    HEAD requests return a simple ``200 OK`` without calling downstream
    dependencies.  Container orchestrators (Azure Container Apps, Kubernetes)
    issue frequent HEAD probes; executing full dependency checks for each one
    would create unnecessary load and telemetry noise.
    """
    if request.method == "HEAD":
        return Response(status_code=200)

    req_id = _request_id(request)
    resources, duration = await _check_all_resources()

    status = _compute_health_status(resources)
    envelope = ResponseEnvelope(
        data={
            "status": status,
            "duration": duration,
            "resources": [
                r.model_dump(exclude_none=True) for r in resources
            ],
        },
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

