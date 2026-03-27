import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import settings
from domains.tenants.models import FREE_TIER
from domains.tenants.service import tenant_service, tier_service, user_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _make_401_response(message: str) -> JSONResponse:
    """Build a standard 401 error response."""
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "UNAUTHORIZED",
                "message": message,
            }
        },
    )


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Tenant context middleware.

    Resolves the current user's tenant and tier from Cosmos DB
    and sets ``request.state.tenant`` and ``request.state.tier``.

    If the user has not yet registered, only ``POST /api/v1/tenants``
    (registration) is allowed; all other routes return 401.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip for health endpoints
        if request.url.path.startswith("/api/v1/health"):
            request.state.tenant = None
            request.state.tier = FREE_TIER
            return await call_next(request)

        external_id = getattr(request.state, "external_id", None)
        if not external_id or external_id == "anonymous":
            request.state.tenant = None
            request.state.tier = FREE_TIER
            return await call_next(request)

        # Dev mode without Cosmos: set stub values
        if settings.skip_auth and not settings.cosmos_db_endpoint:
            request.state.tenant = None
            request.state.tier = FREE_TIER
            return await call_next(request)

        # Look up user by external ID
        user = await user_service.get_user_by_external_id(external_id)

        if user is not None:
            # Load tenant and tier
            tenant = await tenant_service.get_tenant(user.tenant_id)
            if tenant is None:
                return _make_401_response("Tenant not found for this user.")

            tier = tier_service.get_tier(tenant.tier_id)
            request.state.tenant = tenant
            request.state.tier = tier
            structlog.contextvars.bind_contextvars(tenant_id=tenant.id)
        else:
            # User not found — only allow tenant registration
            is_registration = (
                request.method == "POST"
                and request.url.path.rstrip("/") == "/api/v1/tenants"
            )
            if not is_registration:
                return _make_401_response(
                    "User not registered. Create a tenant first via POST /api/v1/tenants."
                )
            request.state.tenant = None
            request.state.tier = FREE_TIER

        return await call_next(request)
