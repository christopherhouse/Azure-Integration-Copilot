import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class QuotaMiddleware(BaseHTTPMiddleware):
    """Quota enforcement middleware stub.

    Currently passes through all requests without enforcement.
    Real quota checking will be implemented in task 004.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        return await call_next(request)
