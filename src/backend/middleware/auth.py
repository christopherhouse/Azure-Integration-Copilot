import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware stub.

    In development, sets ``request.state.user_id`` to a hardcoded dev value.
    Skips authentication for health-check paths.
    Real JWT validation will be implemented in task 004.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Skip auth for health endpoints
        if request.url.path.startswith("/api/v1/health"):
            request.state.user_id = "anonymous"
            return await call_next(request)

        # Stub: accept any Bearer token and set a dev user ID
        auth_header = request.headers.get("Authorization", "")
        if auth_header.startswith("Bearer "):
            request.state.user_id = "dev-user-001"
        else:
            request.state.user_id = "dev-user-001"

        return await call_next(request)
