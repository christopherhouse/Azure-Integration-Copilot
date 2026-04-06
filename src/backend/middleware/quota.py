import re

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from domains.tenants.service import quota_service
from shared.metrics import quota_checks_counter, quota_usage_ratio_histogram
from shared.security_signals import quota_burst_tracker

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Quota rules: (method, path_pattern, limit_name)
_QUOTA_RULES: list[tuple[str, re.Pattern, str]] = [
    ("POST", re.compile(r"^/api/v1/projects/?$"), "max_projects"),
    ("POST", re.compile(r"^/api/v1/projects/[^/]+/artifacts/?$"), "max_total_artifacts"),
    ("POST", re.compile(r"^/api/v1/projects/[^/]+/analyses/?$"), "max_daily_analyses"),
]


class QuotaMiddleware(BaseHTTPMiddleware):
    """Quota enforcement middleware.

    Matches request method + path against quota rules and returns
    429 when a tenant has exceeded their tier limits.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        tenant = getattr(request.state, "tenant", None)
        tier = getattr(request.state, "tier", None)

        if tenant is not None and tier is not None:
            tenant_id = getattr(tenant, "id", "unknown")
            for method, pattern, limit_name in _QUOTA_RULES:
                if request.method == method and pattern.match(request.url.path):
                    result = await quota_service.check(tenant, tier, limit_name)

                    # Record usage ratio for proactive alerting
                    if result.maximum and result.maximum > 0:
                        usage_ratio = result.current / result.maximum
                        quota_usage_ratio_histogram.record(
                            usage_ratio,
                            {"limit_name": limit_name, "tenant_id": tenant_id},
                        )
                        if usage_ratio >= 0.8 and result.allowed:
                            logger.info(
                                "quota_warning",
                                limit_name=limit_name,
                                current=result.current,
                                maximum=result.maximum,
                                usage_ratio=round(usage_ratio, 2),
                                tenant_id=tenant_id,
                            )

                    if not result.allowed:
                        logger.warning(
                            "quota_exceeded",
                            limit_name=limit_name,
                            current=result.current,
                            maximum=result.maximum,
                        )
                        quota_checks_counter.add(
                            1,
                            {"result": "denied", "limit_name": limit_name, "tenant_id": tenant_id},
                        )
                        quota_burst_tracker.record(tenant_id)
                        return JSONResponse(
                            status_code=429,
                            content={
                                "error": {
                                    "code": "QUOTA_EXCEEDED",
                                    "message": f"Quota exceeded for {limit_name}.",
                                    "detail": {
                                        "limit": limit_name,
                                        "current": result.current,
                                        "max": result.maximum,
                                    },
                                }
                            },
                        )
                    quota_checks_counter.add(
                        1,
                        {"result": "allowed", "limit_name": limit_name, "tenant_id": tenant_id},
                    )
                    break  # Only match first rule

        return await call_next(request)
