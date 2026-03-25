import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class TenantContextMiddleware(BaseHTTPMiddleware):
    """Tenant context middleware stub.

    Sets ``request.state.tenant`` and ``request.state.tier`` to hardcoded
    development values.  Real tenant resolution will be implemented in task 004.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        request.state.tenant = "dev-tenant-001"
        request.state.tier = "free"
        return await call_next(request)
