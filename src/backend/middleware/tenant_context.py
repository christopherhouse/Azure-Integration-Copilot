"""Tenant context middleware — auto-provisions tenants on first request."""

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import settings
from domains.tenants.models import FREE_TIER
from domains.tenants.service import tenant_service, tier_service, user_service

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Tenant context middleware.

    Resolves the current user's tenant and tier from Cosmos DB
    and sets ``request.state.tenant`` and ``request.state.tier``.

    If the user has not yet registered, a new tenant and owner user are
    provisioned automatically on the first authenticated API call.
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
                return JSONResponse(
                    status_code=500,
                    content={
                        "error": {
                            "code": "INTERNAL_ERROR",
                            "message": "Tenant not found for this user.",
                        }
                    },
                )

            tier = tier_service.get_tier(tenant.tier_id)
            request.state.tenant = tenant
            request.state.tier = tier
            structlog.contextvars.bind_contextvars(tenant_id=tenant.id)
        else:
            # Auto-provision tenant on first authenticated request
            try:
                email = getattr(request.state, "email", "")
                display_name = getattr(request.state, "display_name", "")
                tenant, _user = await tenant_service.get_or_create_tenant_for_external_user(
                    external_id=external_id,
                    email=email,
                    display_name=display_name,
                )
                tier = tier_service.get_tier(tenant.tier_id)
                request.state.tenant = tenant
                request.state.tier = tier
                structlog.contextvars.bind_contextvars(tenant_id=tenant.id)
                logger.info("tenant_auto_provisioned_via_middleware", tenant_id=tenant.id)
            except Exception:
                logger.exception("tenant_auto_provision_failed", external_id=external_id)
                return JSONResponse(
                    status_code=503,
                    content={
                        "error": {
                            "code": "PROVISIONING_ERROR",
                            "message": "Unable to provision tenant. Please try again.",
                        }
                    },
                )

        return await call_next(request)
