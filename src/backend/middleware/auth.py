import uuid

import httpx
import structlog
from jose import JWTError, jwt
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from config import settings

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

# Dev-mode identity used when SKIP_AUTH=true
_DEV_EXTERNAL_ID = "dev-user-001"
_DEV_EMAIL = "dev@localhost"
_DEV_DISPLAY_NAME = "Dev User"

# JWKS cache
_jwks_cache: dict | None = None


async def _fetch_jwks(tenant_subdomain: str) -> dict:
    """Fetch JWKS from Microsoft Entra External ID (CIAM) discovery endpoint."""
    global _jwks_cache  # noqa: PLW0603
    if _jwks_cache is not None:
        return _jwks_cache

    discovery_url = (
        f"https://{tenant_subdomain}.ciamlogin.com/{tenant_subdomain}.onmicrosoft.com/v2.0/.well-known/openid-configuration"
    )
    async with httpx.AsyncClient() as client:
        discovery = await client.get(discovery_url)
        discovery.raise_for_status()
        jwks_uri = discovery.json()["jwks_uri"]

        jwks_response = await client.get(jwks_uri)
        jwks_response.raise_for_status()
        _jwks_cache = jwks_response.json()

    return _jwks_cache


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

        # Skip auth for health endpoints
        if request.url.path.startswith("/api/v1/health"):
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
            return _make_401_response("Missing or invalid Authorization header.", request_id)

        token = auth_header[7:]

        try:
            # Fetch JWKS and validate token
            jwks = await _fetch_jwks(settings.entra_ciam_tenant_subdomain)
            unverified_header = jwt.get_unverified_header(token)

            # Find the matching key
            rsa_key: dict = {}
            for key in jwks.get("keys", []):
                if key.get("kid") == unverified_header.get("kid"):
                    rsa_key = key
                    break

            if not rsa_key:
                return _make_401_response("Unable to find appropriate signing key.", request_id)

            payload = jwt.decode(
                token,
                rsa_key,
                algorithms=["RS256"],
                audience=settings.entra_ciam_client_id,
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
                return _make_401_response("Token missing required claims.", request_id)

        except JWTError as exc:
            logger.warning("jwt_validation_failed", error=str(exc))
            return _make_401_response("Invalid or expired token.", request_id)
        except httpx.HTTPError as exc:
            logger.error("jwks_fetch_failed", error=str(exc))
            return _make_401_response("Unable to validate token at this time.", request_id)

        return await call_next(request)

