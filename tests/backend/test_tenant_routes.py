"""Tests for tenant CRUD endpoints."""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

_test_env = {
    "ENVIRONMENT": "test",
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "",
    "WEB_PUBSUB_ENDPOINT": "",
    "AZURE_CLIENT_ID": "",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from main import app  # noqa: E402

from domains.tenants.models import Tenant, TenantStatus, Usage, User, UserRole, UserStatus


def _make_tenant(tenant_id: str = "t-001", display_name: str = "Test Tenant") -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id=tenant_id,
        partitionKey=tenant_id,
        displayName=display_name,
        ownerId="u-001",
        tierId="tier_free",
        status=TenantStatus.ACTIVE,
        usage=Usage(daily_analysis_reset_at=now),
        createdAt=now,
        updatedAt=now,
    )


def _make_user(tenant_id: str = "t-001", external_id: str = "dev-user-001") -> User:
    return User(
        id="u-001",
        partitionKey=tenant_id,
        tenantId=tenant_id,
        externalId=external_id,
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        createdAt=datetime.now(UTC),
    )


def _setup_context_mocks(tenant, user=None):
    """Return context manager patches for tenant context middleware."""
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


# ---------------------------------------------------------------------------
# POST /api/v1/tenants — Create tenant (registration)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_tenant_returns_201(client):
    """POST /api/v1/tenants creates a tenant and returns 201."""
    new_tenant = _make_tenant("t-new", "New Tenant")
    new_user = _make_user("t-new")
    auto_tenant = _make_tenant("t-auto", "Auto")
    auto_user = _make_user("t-auto")

    with (
        patch("middleware.tenant_context.user_service") as mock_ctx_user_svc,
        patch("middleware.tenant_context.tenant_service") as mock_ctx_tenant_svc,
        patch("middleware.tenant_context.settings") as mock_settings,
        patch("domains.tenants.router.user_service") as mock_router_user_svc,
        patch("domains.tenants.router.tenant_service") as mock_router_tenant_svc,
    ):
        mock_settings.skip_auth = True
        mock_settings.cosmos_db_endpoint = "https://fake.documents.azure.com/"
        # Middleware: user not found → auto-provision
        mock_ctx_user_svc.get_user_by_external_id = AsyncMock(return_value=None)
        mock_ctx_tenant_svc.get_or_create_tenant_for_external_user = AsyncMock(
            return_value=(auto_tenant, auto_user),
        )
        # Router checks: no existing user → create
        mock_router_user_svc.get_user_by_external_id = AsyncMock(return_value=None)
        mock_router_tenant_svc.create_tenant = AsyncMock(return_value=(new_tenant, new_user))

        response = await client.post(
            "/api/v1/tenants",
            json={"displayName": "New Tenant"},
        )
        assert response.status_code == 201
        body = response.json()
        assert body["data"]["id"] == "t-new"
        assert body["data"]["displayName"] == "New Tenant"
        assert "meta" in body
        assert "request_id" in body["meta"]


@pytest.mark.asyncio
async def test_create_tenant_conflict_when_user_exists(client):
    """POST /api/v1/tenants returns 409 if user already has a tenant."""
    existing_user = _make_user()

    with (
        patch("middleware.tenant_context.user_service") as mock_ctx_user_svc,
        patch("middleware.tenant_context.tenant_service") as mock_ctx_tenant_svc,
        patch("middleware.tenant_context.settings") as mock_settings,
        patch("domains.tenants.router.user_service") as mock_router_user_svc,
    ):
        mock_settings.skip_auth = True
        mock_settings.cosmos_db_endpoint = "https://fake.documents.azure.com/"
        # Middleware finds the user and loads tenant
        mock_ctx_user_svc.get_user_by_external_id = AsyncMock(return_value=existing_user)
        mock_ctx_tenant_svc.get_tenant = AsyncMock(return_value=_make_tenant())
        # Router also finds user → conflict
        mock_router_user_svc.get_user_by_external_id = AsyncMock(return_value=existing_user)

        response = await client.post(
            "/api/v1/tenants",
            json={"displayName": "Another Tenant"},
        )
        assert response.status_code == 409
        body = response.json()
        assert body["error"]["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_create_tenant_requires_display_name(client):
    """POST /api/v1/tenants without displayName returns 422."""
    auto_tenant = _make_tenant("t-auto")
    auto_user = _make_user("t-auto")

    with (
        patch("middleware.tenant_context.user_service") as mock_ctx_user_svc,
        patch("middleware.tenant_context.tenant_service") as mock_ctx_tenant_svc,
        patch("middleware.tenant_context.settings") as mock_settings,
    ):
        mock_settings.skip_auth = True
        mock_settings.cosmos_db_endpoint = "https://fake.documents.azure.com/"
        mock_ctx_user_svc.get_user_by_external_id = AsyncMock(return_value=None)
        mock_ctx_tenant_svc.get_or_create_tenant_for_external_user = AsyncMock(
            return_value=(auto_tenant, auto_user),
        )

        response = await client.post(
            "/api/v1/tenants",
            json={},
        )
        assert response.status_code == 422


# ---------------------------------------------------------------------------
# GET /api/v1/tenants/me — Get current tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_tenant_me_returns_tenant(client):
    """GET /api/v1/tenants/me returns the current user's tenant."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        response = await client.get("/api/v1/tenants/me")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == "t-001"
        assert body["data"]["displayName"] == "Test Tenant"
        assert "usage" in body["data"]
        usage = body["data"]["usage"]
        assert "projectCount" in usage
        assert "totalArtifactCount" in usage
        assert "dailyAnalysisCount" in usage


@pytest.mark.asyncio
async def test_get_tenant_me_returns_404_when_no_tenant(client):
    """GET /api/v1/tenants/me returns 404 when tenant is None (dev mode, no Cosmos)."""
    response = await client.get("/api/v1/tenants/me")
    # In SKIP_AUTH mode without Cosmos, tenant is None → 404
    assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/tenants/me — Update tenant
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_patch_tenant_me_updates_display_name(client):
    """PATCH /api/v1/tenants/me updates the tenant display name."""
    tenant = _make_tenant()
    updated_tenant = _make_tenant(display_name="Updated Name")

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.tenants.router.tenant_service") as mock_tenant_svc:
            mock_tenant_svc.update_tenant_display_name = AsyncMock(return_value=updated_tenant)

            response = await client.patch(
                "/api/v1/tenants/me",
                json={"displayName": "Updated Name"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["data"]["displayName"] == "Updated Name"


@pytest.mark.asyncio
async def test_patch_tenant_me_returns_404_when_no_tenant(client):
    """PATCH /api/v1/tenants/me returns 404 when no tenant context."""
    response = await client.patch(
        "/api/v1/tenants/me",
        json={"displayName": "Updated"},
    )
    # In SKIP_AUTH mode without Cosmos, tenant is None → 404
    assert response.status_code == 404


def test_tenant_routes_registered():
    """Tenant routes are registered in the app."""
    routes = [route.path for route in app.routes if hasattr(route, "path")]
    assert "/api/v1/tenants" in routes
    assert "/api/v1/tenants/me" in routes
