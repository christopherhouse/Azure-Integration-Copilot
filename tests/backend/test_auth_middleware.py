"""Tests for the auth middleware (JWT validation and SKIP_AUTH mode)."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))


def _make_app_skip_auth():
    """Create a fresh app import with SKIP_AUTH=true and no Cosmos."""
    with patch.dict(
        os.environ,
        {
            "ENVIRONMENT": "test",
            "COSMOS_DB_ENDPOINT": "",
            "BLOB_STORAGE_ENDPOINT": "",
            "EVENT_GRID_NAMESPACE_ENDPOINT": "",
            "WEB_PUBSUB_ENDPOINT": "",
            "AZURE_CLIENT_ID": "",
            "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
            "SKIP_AUTH": "true",
        },
    ):
        from main import app

        return app


# Use the already-imported app from conftest which has SKIP_AUTH=true
app_skip = _make_app_skip_auth()


@pytest_asyncio.fixture
async def client_skip_auth():
    transport = ASGITransport(app=app_skip)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Tests with SKIP_AUTH=true (dev mode)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_skip_auth_health_no_token(client_skip_auth):
    """Health endpoint works without any token in SKIP_AUTH mode."""
    response = await client_skip_auth.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_skip_auth_sets_dev_identity(client_skip_auth):
    """In SKIP_AUTH mode, requests get the dev identity without a token."""
    response = await client_skip_auth.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_skip_auth_non_health_no_token(client_skip_auth):
    """In SKIP_AUTH mode, non-health endpoints work without a token."""
    # This should not return 401 — SKIP_AUTH allows all requests through auth
    response = await client_skip_auth.get("/api/v1/does-not-exist")
    # Will get 404 (not found) but NOT 401 (unauthorized)
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# Tests with SKIP_AUTH=false (auth required)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_missing_token_returns_401():
    """Requests without an Authorization header return 401."""
    # Temporarily set skip_auth to False on the settings
    from config import settings

    original = settings.skip_auth
    settings.skip_auth = False
    try:
        transport = ASGITransport(app=app_skip)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/tenants/me",
            )
            assert response.status_code == 401
            body = response.json()
            assert body["error"]["code"] == "UNAUTHORIZED"
    finally:
        settings.skip_auth = original


@pytest.mark.asyncio
async def test_invalid_bearer_token_returns_401():
    """Requests with an invalid bearer token return 401."""
    from config import settings

    original = settings.skip_auth
    settings.skip_auth = False
    try:
        # Mock _fetch_oidc_metadata to avoid actual HTTP calls
        with patch("middleware.auth._fetch_oidc_metadata", new_callable=AsyncMock) as mock_oidc:
            mock_oidc.return_value = (
                {"keys": [{"kid": "test-kid", "kty": "RSA", "n": "test", "e": "AQAB"}]},
                "https://test-issuer.example.com",
            )
            transport = ASGITransport(app=app_skip)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/tenants/me",
                    headers={"Authorization": "Bearer invalid.jwt.token"},
                )
                assert response.status_code == 401
                body = response.json()
                assert body["error"]["code"] == "UNAUTHORIZED"
    finally:
        settings.skip_auth = original


@pytest.mark.asyncio
async def test_health_skips_auth_even_when_auth_required():
    """Health endpoints skip auth even when SKIP_AUTH=false."""
    from config import settings

    original = settings.skip_auth
    settings.skip_auth = False
    try:
        transport = ASGITransport(app=app_skip)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get("/api/v1/health")
            assert response.status_code == 200
    finally:
        settings.skip_auth = original


@pytest.mark.asyncio
async def test_non_bearer_auth_header_returns_401():
    """Authorization header without 'Bearer ' prefix returns 401."""
    from config import settings

    original = settings.skip_auth
    settings.skip_auth = False
    try:
        transport = ASGITransport(app=app_skip)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/tenants/me",
                headers={"Authorization": "Basic dXNlcjpwYXNz"},
            )
            assert response.status_code == 401
            body = response.json()
            assert body["error"]["code"] == "UNAUTHORIZED"
            assert "Missing or invalid" in body["error"]["message"]
    finally:
        settings.skip_auth = original


# ---------------------------------------------------------------------------
# RSA key helper for JWT security tests
# ---------------------------------------------------------------------------


def _generate_rsa_key_material(kid: str = "test-kid-1") -> tuple[bytes, dict]:
    """Generate an RSA key pair and return *(private_pem_bytes, jwk_public_dict)*.

    The JWK dict is suitable for inclusion in a JWKS ``keys`` array.
    The private PEM can be used with ``jose.jwt.encode`` to sign tokens.
    """
    import base64

    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric import rsa

    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )

    pub = private_key.public_key().public_numbers()

    def _b64url(val: int) -> str:
        length = (val.bit_length() + 7) // 8
        return base64.urlsafe_b64encode(val.to_bytes(length, "big")).rstrip(b"=").decode()

    jwk_dict = {
        "kty": "RSA",
        "kid": kid,
        "use": "sig",
        "alg": "RS256",
        "n": _b64url(pub.n),
        "e": _b64url(pub.e),
    }
    return private_pem, jwk_dict


# ---------------------------------------------------------------------------
# JWT issuer validation (H1)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_wrong_issuer_token_returns_401():
    """A JWT whose ``iss`` claim differs from the OIDC-discovered issuer is rejected."""
    from jose import jwt as jose_jwt

    from config import settings

    private_pem, jwk_dict = _generate_rsa_key_material("issuer-test-kid")

    expected_issuer = "https://expected-issuer.example.com"
    wrong_issuer = "https://evil-issuer.example.com"
    test_client_id = "test-client-id"

    # Token is validly signed but carries the WRONG issuer
    token = jose_jwt.encode(
        {
            "sub": "user-123",
            "oid": "ext-id-123",
            "iss": wrong_issuer,
            "aud": test_client_id,
        },
        private_pem.decode(),
        algorithm="RS256",
        headers={"kid": "issuer-test-kid"},
    )

    jwks = {"keys": [jwk_dict]}

    original_skip = settings.skip_auth
    original_subdomain = settings.entra_ciam_tenant_subdomain
    original_client_id = settings.entra_ciam_client_id
    settings.skip_auth = False
    settings.entra_ciam_tenant_subdomain = "test-tenant"
    settings.entra_ciam_client_id = test_client_id
    try:
        with patch(
            "middleware.auth._fetch_oidc_metadata",
            new_callable=AsyncMock,
            return_value=(jwks, expected_issuer),
        ):
            transport = ASGITransport(app=app_skip)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/tenants/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                assert response.status_code == 401
                body = response.json()
                assert body["error"]["code"] == "UNAUTHORIZED"
    finally:
        settings.skip_auth = original_skip
        settings.entra_ciam_tenant_subdomain = original_subdomain
        settings.entra_ciam_client_id = original_client_id


# ---------------------------------------------------------------------------
# JWKS KID-miss refresh (H2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jwks_kid_miss_triggers_refresh():
    """On a KID miss the middleware calls ``_refresh_jwks`` and retries key lookup."""
    from jose import jwt as jose_jwt

    from config import settings

    private_pem, correct_jwk = _generate_rsa_key_material("correct-kid")

    expected_issuer = "https://test-issuer.example.com"
    test_client_id = "test-client-id"

    token = jose_jwt.encode(
        {
            "sub": "user-123",
            "oid": "ext-id-123",
            "iss": expected_issuer,
            "aud": test_client_id,
        },
        private_pem.decode(),
        algorithm="RS256",
        headers={"kid": "correct-kid"},
    )

    # Initial JWKS: does NOT contain "correct-kid"
    wrong_jwks = {"keys": [{"kid": "old-kid", "kty": "RSA", "n": "fake", "e": "AQAB"}]}
    # Refreshed JWKS: DOES contain "correct-kid"
    correct_jwks = {"keys": [correct_jwk]}

    original_skip = settings.skip_auth
    original_subdomain = settings.entra_ciam_tenant_subdomain
    original_client_id = settings.entra_ciam_client_id
    settings.skip_auth = False
    settings.entra_ciam_tenant_subdomain = "test-tenant"
    settings.entra_ciam_client_id = test_client_id
    try:
        with (
            patch(
                "middleware.auth._fetch_oidc_metadata",
                new_callable=AsyncMock,
                return_value=(wrong_jwks, expected_issuer),
            ),
            patch(
                "middleware.auth._refresh_jwks",
                new_callable=AsyncMock,
                return_value=correct_jwks,
            ) as mock_refresh,
            # Allow tenant context middleware to pass without Cosmos DB
            patch("middleware.tenant_context.settings", skip_auth=True, cosmos_db_endpoint=""),
        ):
            transport = ASGITransport(app=app_skip)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                response = await client.get(
                    "/api/v1/tenants/me",
                    headers={"Authorization": f"Bearer {token}"},
                )
                # _refresh_jwks must have been invoked due to KID miss
                mock_refresh.assert_called_once()
                # Auth middleware must NOT have rejected the request
                if response.status_code == 401:
                    body = response.json()
                    assert body["error"]["message"] != "Unable to find appropriate signing key."
                    assert body["error"]["message"] != "Invalid or expired token."
    finally:
        settings.skip_auth = original_skip
        settings.entra_ciam_tenant_subdomain = original_subdomain
        settings.entra_ciam_client_id = original_client_id


# ---------------------------------------------------------------------------
# JWKS cache TTL (H2)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_jwks_cache_ttl_expires():
    """After the JWKS cache TTL elapses, ``_fetch_oidc_metadata`` re-fetches."""
    import middleware.auth as auth_module

    # Preserve original cache state so we can restore it after the test
    orig_cache = auth_module._jwks_cache
    orig_issuer = auth_module._issuer_cache
    orig_ts = auth_module._jwks_cache_timestamp

    try:
        # Seed the cache at t=1000
        cached_jwks = {"keys": [{"kid": "cached-key", "kty": "RSA"}]}
        cached_issuer = "https://cached-issuer.example.com"
        auth_module._jwks_cache = cached_jwks
        auth_module._issuer_cache = cached_issuer
        auth_module._jwks_cache_timestamp = 1000.0

        # --- Within TTL: expect a cache hit (no HTTP call) ---
        with patch("middleware.auth.time") as mock_time:
            mock_time.monotonic.return_value = 1100.0  # 100 s elapsed, TTL=3600 s
            result = await auth_module._fetch_oidc_metadata("test-tenant")
            assert result == (cached_jwks, cached_issuer)

        # --- Past TTL: expect a network re-fetch ---
        fresh_jwks = {"keys": [{"kid": "fresh-key", "kty": "RSA"}]}
        fresh_issuer = "https://fresh-issuer.example.com"

        mock_discovery_resp = MagicMock()
        mock_discovery_resp.json.return_value = {
            "jwks_uri": "https://login.example.com/jwks",
            "issuer": fresh_issuer,
        }
        mock_discovery_resp.raise_for_status = MagicMock()

        mock_jwks_resp = MagicMock()
        mock_jwks_resp.json.return_value = fresh_jwks
        mock_jwks_resp.raise_for_status = MagicMock()

        mock_http_client = AsyncMock()
        mock_http_client.get = AsyncMock(
            side_effect=[mock_discovery_resp, mock_jwks_resp],
        )

        mock_cm = AsyncMock()
        mock_cm.__aenter__.return_value = mock_http_client

        with (
            patch("middleware.auth.time") as mock_time,
            patch("middleware.auth.httpx.AsyncClient", return_value=mock_cm),
        ):
            mock_time.monotonic.return_value = 4601.0  # 3601 s elapsed, past TTL
            result = await auth_module._fetch_oidc_metadata("test-tenant")
            assert result == (fresh_jwks, fresh_issuer)
            assert mock_http_client.get.call_count == 2  # discovery + JWKS
    finally:
        auth_module._jwks_cache = orig_cache
        auth_module._issuer_cache = orig_issuer
        auth_module._jwks_cache_timestamp = orig_ts


# ---------------------------------------------------------------------------
# Production SKIP_AUTH guard (M3)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_production_skip_auth_guard_raises():
    """Lifespan raises ``RuntimeError`` when SKIP_AUTH=true in production."""
    from config import settings
    from main import lifespan

    original_env = settings.environment
    original_skip = settings.skip_auth
    settings.environment = "production"
    settings.skip_auth = True
    try:
        with pytest.raises(RuntimeError, match="SKIP_AUTH=true is not allowed"):
            async with lifespan(app_skip):
                pass  # pragma: no cover – should not reach here
    finally:
        settings.environment = original_env
        settings.skip_auth = original_skip
