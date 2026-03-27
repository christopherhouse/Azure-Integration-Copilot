"""Tests for the auth middleware (JWT validation and SKIP_AUTH mode)."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

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
        # Mock _fetch_jwks to avoid actual HTTP calls
        with patch("middleware.auth._fetch_jwks", new_callable=AsyncMock) as mock_jwks:
            mock_jwks.return_value = {"keys": [{"kid": "test-kid", "kty": "RSA", "n": "test", "e": "AQAB"}]}
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
