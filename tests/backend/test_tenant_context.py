"""Tests for tenant context middleware — tenant resolution and auto-provisioning."""

import os
import sys
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

from datetime import UTC, datetime

from domains.tenants.models import FREE_TIER, Tenant, TenantStatus, Usage, User, UserRole, UserStatus


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


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_tenant_resolved_for_known_user(client):
    """When user exists in Cosmos, tenant and tier are set on request state."""
    tenant = _make_tenant()
    user = _make_user()

    with (
        patch("middleware.tenant_context.user_service") as mock_user_svc,
        patch("middleware.tenant_context.tenant_service") as mock_tenant_svc,
        patch("middleware.tenant_context.settings") as mock_settings,
    ):
        mock_settings.skip_auth = True
        mock_settings.cosmos_db_endpoint = "https://fake.documents.azure.com/"
        mock_user_svc.get_user_by_external_id = AsyncMock(return_value=user)
        mock_tenant_svc.get_tenant = AsyncMock(return_value=tenant)

        response = await client.get("/api/v1/tenants/me")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == "t-001"
        assert body["data"]["displayName"] == "Test Tenant"


@pytest.mark.asyncio
async def test_new_user_auto_provisioned(client):
    """First request by a new user auto-creates tenant/user and proceeds (200)."""
    tenant = _make_tenant("t-auto")
    user = _make_user("t-auto")

    with (
        patch("middleware.tenant_context.user_service") as mock_user_svc,
        patch("middleware.tenant_context.tenant_service") as mock_tenant_svc,
        patch("middleware.tenant_context.settings") as mock_settings,
    ):
        mock_settings.skip_auth = True
        mock_settings.cosmos_db_endpoint = "https://fake.documents.azure.com/"
        mock_user_svc.get_user_by_external_id = AsyncMock(return_value=None)
        mock_tenant_svc.get_or_create_tenant_for_external_user = AsyncMock(
            return_value=(tenant, user),
        )

        response = await client.get("/api/v1/tenants/me")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["id"] == "t-auto"
        mock_tenant_svc.get_or_create_tenant_for_external_user.assert_awaited_once()


@pytest.mark.asyncio
async def test_auto_provision_failure_returns_503(client):
    """Provisioning failure returns a controlled 503 error."""
    with (
        patch("middleware.tenant_context.user_service") as mock_user_svc,
        patch("middleware.tenant_context.tenant_service") as mock_tenant_svc,
        patch("middleware.tenant_context.settings") as mock_settings,
    ):
        mock_settings.skip_auth = True
        mock_settings.cosmos_db_endpoint = "https://fake.documents.azure.com/"
        mock_user_svc.get_user_by_external_id = AsyncMock(return_value=None)
        mock_tenant_svc.get_or_create_tenant_for_external_user = AsyncMock(
            side_effect=RuntimeError("Cosmos DB unavailable"),
        )

        response = await client.get("/api/v1/tenants/me")
        assert response.status_code == 503
        body = response.json()
        assert body["error"]["code"] == "PROVISIONING_ERROR"


@pytest.mark.asyncio
async def test_health_skips_tenant_resolution(client):
    """Health endpoints don't require tenant resolution."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_feature_flags_skips_tenant_resolution(client):
    """Feature flags endpoint doesn't require tenant resolution."""
    with patch("domains.feature_flags.router.app_config_service") as mock_svc:
        mock_svc.ensure_loaded = AsyncMock()
        mock_svc.get_feature_flags.return_value = {"myFlag": True}
        response = await client.get("/api/v1/feature-flags")

    assert response.status_code == 200
    body = response.json()
    assert body["data"]["flags"]["myFlag"] is True


@pytest.mark.asyncio
async def test_tier_resolved_as_free_tier(client):
    """The resolved tier should be the FREE_TIER for MVP."""
    tenant = _make_tenant()
    user = _make_user()

    with (
        patch("middleware.tenant_context.user_service") as mock_user_svc,
        patch("middleware.tenant_context.tenant_service") as mock_tenant_svc,
        patch("middleware.tenant_context.settings") as mock_settings,
    ):
        mock_settings.skip_auth = True
        mock_settings.cosmos_db_endpoint = "https://fake.documents.azure.com/"
        mock_user_svc.get_user_by_external_id = AsyncMock(return_value=user)
        mock_tenant_svc.get_tenant = AsyncMock(return_value=tenant)

        response = await client.get("/api/v1/tenants/me")
        assert response.status_code == 200
        body = response.json()
        assert body["data"]["tierId"] == FREE_TIER.id
