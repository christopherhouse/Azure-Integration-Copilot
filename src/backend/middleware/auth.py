import time
import uuid

import httpx
import structlog
from jose import JWTError, jwt
from opentelemetry import baggage, context, trace
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import settings
from shared.metrics import auth_attempts_counter
from shared.security_signals import auth_failure_tracker

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _set_auth_span_attributes(*, result: str, failure_reason: str = "", token_issuer: str = "") -> None:
    """Set authentication-related attributes on the current OpenTelemetry span."""
    span = trace.get_current_span()
    if span and span.is_recording():
        span.set_attribute("auth.result", result)
        if failure_reason:
            span.set_attribute("auth.failure_reason", failure_reason)
        if token_issuer:
            span.set_attribute("auth.token_issuer", token_issuer)

# Dev-mode identity used when SKIP_AUTH=true
_DEV_EXTERNAL_ID = "dev-user-001"
_DEV_EMAIL = "dev@localhost"
_DEV_DISPLAY_NAME = "Dev User"

# JWKS + OIDC metadata cache with TTL
_JWKS_CACHE_TTL_SECONDS = 3600  # 60 minutes

_jwks_cache: dict | None = None
_jwks_cache_timestamp: float = 0.0
_issuer_cache: str | None = None


async def _fetch_oidc_metadata(tenant_subdomain: str) -> tuple[dict, str]:
    """Fetch JWKS and issuer from Microsoft Entra External ID (CIAM) OIDC discovery endpoint.

    Returns (jwks_dict, issuer_string).
    """
    global _jwks_cache, _jwks_cache_timestamp, _issuer_cache  # noqa: PLW0603

    now = time.monotonic()
    cache_valid = (
        _jwks_cache is not None
        and _issuer_cache is not None
        and (now - _jwks_cache_timestamp) < _JWKS_CACHE_TTL_SECONDS
    )
    if cache_valid:
        return _jwks_cache, _issuer_cache

    discovery_url = (
        f"https://{tenant_subdomain}.ciamlogin.com/{tenant_subdomain}.onmicrosoft.com/v2.0/.well-known/openid-configuration"
    )
    async with httpx.AsyncClient() as client:
        discovery = await client.get(discovery_url)
        discovery.raise_for_status()
        discovery_data = discovery.json()
        jwks_uri = discovery_data["jwks_uri"]
        issuer = discovery_data["issuer"]

        jwks_response = await client.get(jwks_uri)
        jwks_response.raise_for_status()
        _jwks_cache = jwks_response.json()
        _issuer_cache = issuer
        _jwks_cache_timestamp = now

    return _jwks_cache, _issuer_cache


async def _refresh_jwks(tenant_subdomain: str) -> dict:
    """Force-refresh the JWKS cache (e.g. on KID miss) and return updated JWKS."""
    global _jwks_cache, _jwks_cache_timestamp, _issuer_cache  # noqa: PLW0603
    _jwks_cache = None
    _issuer_cache = None
    _jwks_cache_timestamp = 0.0
    jwks, _ = await _fetch_oidc_metadata(tenant_subdomain)
    return jwks


def _find_signing_key(jwks: dict, kid: str) -> dict:
    """Find a signing key by KID in the JWKS keyset."""
    for key in jwks.get("keys", []):
        if key.get("kid") == kid:
            return key
    return {}


def _make_401_response(message: str, request_id: str) -> JSONResponse:
    """Build a standard 401 error response."""
    return JSONResponse(
        status_code=401,
        content={
            "error": {
                "code": "UNAUTHORIZED",
                "message": message,
                "request_id": request_id,
            }
        },
    )


class AuthMiddleware(BaseHTTPMiddleware):
    """Authentication middleware.

    Validates JWT tokens from Microsoft Entra External ID (CIAM).
    Supports ``SKIP_AUTH=true`` environment variable for local development.
    Skips authentication for health-check paths.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        # Bind request_id to structlog context so all log entries include it
        request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
        structlog.contextvars.clear_contextvars()
        structlog.contextvars.bind_contextvars(request_id=request_id)

        # Extract frontend trace ID for correlation.
        # The frontend sends X-Trace-ID to link user actions with backend
        # operations. We add this to OpenTelemetry baggage so it flows through
        # the entire request trace and appears in all downstream spans/logs.
        frontend_trace_id = request.headers.get("X-Trace-ID")
        if frontend_trace_id:
            span = trace.get_current_span()
            if span and span.is_recording():
                span.set_attribute("frontend.trace_id", frontend_trace_id)
            # Also set as baggage so it propagates to child spans
            ctx = baggage.set_baggage("frontend.trace_id", frontend_trace_id)
            token = context.attach(ctx)
        else:
            token = None

        try:
            # Skip auth for health, feature flags, and OpenAPI documentation endpoints.
            # Feature flags are global configuration (not user-specific) that the
            # frontend needs before and during authentication to gate UI elements.
            skip_paths = (
                request.url.path.startswith("/api/v1/health")
                or request.url.path.startswith("/api/v1/feature-flags")
                or request.url.path in ("/docs", "/redoc", "/openapi.json")
            )
            if skip_paths:
                request.state.external_id = "anonymous"
                request.state.email = ""
                request.state.display_name = ""
                return await call_next(request)

            # Dev mode: skip JWT validation
            if settings.skip_auth:
                request.state.external_id = _DEV_EXTERNAL_ID
                request.state.email = _DEV_EMAIL
                request.state.display_name = _DEV_DISPLAY_NAME
                return await call_next(request)

            # Extract Bearer token
            auth_header = request.headers.get("Authorization", "")
            if not auth_header.startswith("Bearer "):
                logger.warning(
                    "auth_failure",
                    auth_failure_reason="missing_header",
                    auth_request_path=request.url.path,
                )
                _set_auth_span_attributes(result="failure", failure_reason="missing_header")
                auth_attempts_counter.add(1, {"result": "failure", "failure_reason": "missing_header"})
                auth_failure_tracker.record(request.client.host if request.client else "unknown")
                return _make_401_response("Missing or invalid Authorization header.", request_id)

            jwt_token = auth_header[7:]

            try:
                # Fetch JWKS and OIDC issuer, with TTL-based caching
                jwks, issuer = await _fetch_oidc_metadata(settings.entra_ciam_tenant_subdomain)
                unverified_header = jwt.get_unverified_header(jwt_token)
                kid = unverified_header.get("kid")

                # Find the matching key; on KID miss, refresh JWKS once before rejecting
                rsa_key = _find_signing_key(jwks, kid)
                if not rsa_key:
                    logger.info("jwks_kid_miss_refreshing", kid=kid)
                    jwks = await _refresh_jwks(settings.entra_ciam_tenant_subdomain)
                    rsa_key = _find_signing_key(jwks, kid)

                if not rsa_key:
                    logger.warning(
                        "auth_failure",
                        auth_failure_reason="key_not_found",
                        auth_request_path=request.url.path,
                        kid=kid,
                    )
                    _set_auth_span_attributes(result="failure", failure_reason="key_not_found")
                    auth_attempts_counter.add(1, {"result": "failure", "failure_reason": "key_not_found"})
                    auth_failure_tracker.record(request.client.host if request.client else "unknown")
                    return _make_401_response("Unable to find appropriate signing key.", request_id)

                payload = jwt.decode(
                    jwt_token,
                    rsa_key,
                    algorithms=["RS256"],
                    audience=settings.entra_ciam_client_id,
                    issuer=issuer,
                )

                request.state.external_id = payload.get("oid", payload.get("sub", ""))

                # CIAM tokens may carry the email in the singular "email" claim,
                # the "emails" array claim, or "preferred_username".
                raw_emails = payload.get("emails")
                emails_claim = raw_emails if isinstance(raw_emails, list) else []
                request.state.email = (
                    payload.get("email")
                    or (emails_claim[0] if len(emails_claim) > 0 else None)
                    or payload.get("preferred_username")
                    or ""
                )

                request.state.display_name = payload.get(
                    "name", payload.get("preferred_username", "")
                )

                if not request.state.external_id:
                    logger.warning(
                        "auth_failure",
                        auth_failure_reason="missing_claims",
                        auth_request_path=request.url.path,
                    )
                    _set_auth_span_attributes(result="failure", failure_reason="missing_claims")
                    auth_attempts_counter.add(1, {"result": "failure", "failure_reason": "missing_claims"})
                    auth_failure_tracker.record(request.client.host if request.client else "unknown")
                    return _make_401_response("Token missing required claims.", request_id)

            except JWTError as exc:
                logger.warning("auth_failure", auth_failure_reason="invalid_token", error=str(exc))
                _set_auth_span_attributes(result="failure", failure_reason="invalid_token")
                auth_attempts_counter.add(1, {"result": "failure", "failure_reason": "invalid_token"})
                auth_failure_tracker.record(request.client.host if request.client else "unknown")
                return _make_401_response("Invalid or expired token.", request_id)
            except httpx.HTTPError as exc:
                logger.error("auth_failure", auth_failure_reason="jwks_fetch_failed", error=str(exc))
                _set_auth_span_attributes(result="failure", failure_reason="jwks_fetch_failed")
                auth_attempts_counter.add(1, {"result": "failure", "failure_reason": "jwks_fetch_failed"})
                auth_failure_tracker.record(request.client.host if request.client else "unknown")
                return _make_401_response("Unable to validate token at this time.", request_id)

            _set_auth_span_attributes(result="success")
            auth_attempts_counter.add(1, {"result": "success", "failure_reason": ""})
            return await call_next(request)
        finally:
            if token is not None:
                context.detach(token)

