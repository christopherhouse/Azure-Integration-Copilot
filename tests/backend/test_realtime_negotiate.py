"""Tests for the realtime negotiate endpoint."""

import os
from datetime import UTC, datetime
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

_test_env = {
    "ENVIRONMENT": "test",
    "COSMOS_DB_ENDPOINT": "",
    "BLOB_STORAGE_ENDPOINT": "",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "",
    "WEB_PUBSUB_ENDPOINT": "",
    "AZURE_CLIENT_ID": "",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from main import app
    from domains.realtime.router import realtime_service
    from domains.tenants.models import Tenant, TenantStatus, Usage, User, UserRole, UserStatus


def _make_tenant(tenant_id: str = "t-001") -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id=tenant_id,
        partitionKey=tenant_id,
        displayName="Test Tenant",
        ownerId="u-001",
        tierId="tier_free",
        status=TenantStatus.ACTIVE,
        usage=Usage(daily_analysis_reset_at=now),
        createdAt=now,
        updatedAt=now,
    )


def _make_user(tenant_id: str = "t-001") -> User:
    return User(
        id="u-001",
        partitionKey=tenant_id,
        tenantId=tenant_id,
        externalId="dev-user-001",
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        createdAt=datetime.now(UTC),
    )


def _setup_context_mocks(tenant, user=None):
    if user is None:
        user = _make_user(tenant.id if tenant else "t-001")
    return (
        patch("middleware.tenant_context.user_service", **{
            "get_user_by_external_id": AsyncMock(return_value=user),
        }),
        patch("middleware.tenant_context.tenant_service", **{
            "get_tenant": AsyncMock(return_value=tenant),
        }),
        patch("middleware.tenant_context.settings", **{
            "skip_auth": True,
            "cosmos_db_endpoint": "https://fake.documents.azure.com/",
        }),
    )


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


class TestNegotiateEndpoint:
    """Tests for POST /api/v1/realtime/negotiate."""

    @pytest.mark.asyncio
    async def test_returns_token_url(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                realtime_service,
                "generate_client_token",
                new_callable=AsyncMock,
                return_value={"url": "wss://fake-pubsub.webpubsub.azure.com/client/hubs/notifications?access_token=abc123"},
            ):
                resp = await client.post("/api/v1/realtime/negotiate")

        assert resp.status_code == 200
        body = resp.json()
        assert "url" in body["data"]
        assert "wss://" in body["data"]["url"]

    @pytest.mark.asyncio
    async def test_passes_user_id_and_groups(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                realtime_service,
                "generate_client_token",
                new_callable=AsyncMock,
                return_value={"url": "wss://fake-pubsub/token"},
            ) as mock_gen:
                await client.post("/api/v1/realtime/negotiate")

        mock_gen.assert_awaited_once()
        call_kwargs = mock_gen.call_args.kwargs
        # user_id comes from request.state.user_id which defaults to the
        # User object's id set by the tenant context middleware via user.id.
        # In skip_auth dev mode with no middleware setting user_id, it's "unknown".
        assert isinstance(call_kwargs["user_id"], str)
        assert f"tenant:{tenant.id}" in call_kwargs["groups"]

    @pytest.mark.asyncio
    async def test_returns_401_when_no_tenant_context(self, client):
        """When auth is skipped and cosmos_db_endpoint is empty, tenant is None → 401."""
        resp = await client.post("/api/v1/realtime/negotiate")

        assert resp.status_code == 401
        body = resp.json()
        assert body["error"]["code"] == "UNAUTHORIZED"

    @pytest.mark.asyncio
    async def test_includes_meta_in_response(self, client):
        tenant = _make_tenant()
        mock1, mock2, mock3 = _setup_context_mocks(tenant)
        with mock1, mock2, mock3:
            with patch.object(
                realtime_service,
                "generate_client_token",
                new_callable=AsyncMock,
                return_value={"url": "wss://fake-pubsub/token"},
            ):
                resp = await client.post("/api/v1/realtime/negotiate")

        body = resp.json()
        assert "meta" in body
        assert "request_id" in body["meta"]
        assert "timestamp" in body["meta"]


class TestRealtimeRoutesRegistered:
    """Verify realtime routes are registered in the FastAPI app."""

    @pytest.mark.asyncio
    async def test_negotiate_route_exists(self, client):
        routes = [r.path for r in app.routes]
        assert "/api/v1/realtime/negotiate" in routes
