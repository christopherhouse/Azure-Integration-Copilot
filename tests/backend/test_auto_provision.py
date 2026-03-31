"""Tests for idempotent auto-provisioning — service-layer logic."""

import os
import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

with patch.dict(os.environ, {
    "ENVIRONMENT": "test",
    "COSMOS_DB_ENDPOINT": "",
    "BLOB_STORAGE_ENDPOINT": "",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "",
    "WEB_PUBSUB_ENDPOINT": "",
    "AZURE_CLIENT_ID": "",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
    "SKIP_AUTH": "true",
}):
    pass  # ensure settings are loaded before imports

from datetime import UTC, datetime

from azure.cosmos import exceptions as cosmos_exceptions

from domains.tenants.models import Tenant, TenantStatus, Usage, User, UserRole, UserStatus
from domains.tenants.service import TenantService


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


def _make_user(tenant_id: str = "t-001", external_id: str = "ext-001") -> User:
    return User(
        id="u-001",
        partitionKey=tenant_id,
        tenantId=tenant_id,
        externalId=external_id,
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        createdAt=datetime.now(UTC),
    )


# ---------------------------------------------------------------------------
# get_or_create_tenant_for_external_user — unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_returns_existing_tenant_when_user_found():
    """If user already exists, return the existing tenant without creating."""
    svc = TenantService()
    existing_tenant = _make_tenant()
    existing_user = _make_user()

    with patch("domains.tenants.service.tenant_repository") as mock_repo:
        mock_repo.get_user_by_external_id = AsyncMock(return_value=existing_user)
        mock_repo.get_tenant = AsyncMock(return_value=existing_tenant)

        tenant, user = await svc.get_or_create_tenant_for_external_user("ext-001")

        assert tenant.id == "t-001"
        assert user.external_id == "ext-001"
        mock_repo.create_tenant_and_user.assert_not_called()


@pytest.mark.asyncio
async def test_creates_new_tenant_when_user_not_found():
    """If user does not exist, create a new tenant + user atomically."""
    svc = TenantService()
    new_tenant = _make_tenant("t-new")
    new_user = _make_user("t-new", "ext-new")

    with patch("domains.tenants.service.tenant_repository") as mock_repo:
        mock_repo.get_user_by_external_id = AsyncMock(return_value=None)
        mock_repo.create_tenant_and_user = AsyncMock(return_value=(new_tenant, new_user))

        tenant, user = await svc.get_or_create_tenant_for_external_user(
            external_id="ext-new",
            email="user@example.com",
            display_name="New User",
        )

        assert tenant.id == "t-new"
        mock_repo.create_tenant_and_user.assert_awaited_once()
        # Verify the tenant was built with the display name
        call_args = mock_repo.create_tenant_and_user.call_args
        built_tenant = call_args[0][0]
        built_user = call_args[0][1]
        assert built_tenant.display_name == "New User"
        assert built_user.email == "user@example.com"
        assert built_user.display_name == "New User"


@pytest.mark.asyncio
async def test_uses_email_as_fallback_display_name():
    """When display_name is empty, email is used for the tenant display name."""
    svc = TenantService()
    new_tenant = _make_tenant("t-new")
    new_user = _make_user("t-new", "ext-new")

    with patch("domains.tenants.service.tenant_repository") as mock_repo:
        mock_repo.get_user_by_external_id = AsyncMock(return_value=None)
        mock_repo.create_tenant_and_user = AsyncMock(return_value=(new_tenant, new_user))

        await svc.get_or_create_tenant_for_external_user(
            external_id="ext-new",
            email="user@example.com",
        )

        call_args = mock_repo.create_tenant_and_user.call_args
        built_tenant = call_args[0][0]
        assert built_tenant.display_name == "user@example.com"


@pytest.mark.asyncio
async def test_uses_external_id_as_last_resort_display_name():
    """When both display_name and email are empty, external_id is used."""
    svc = TenantService()
    new_tenant = _make_tenant("t-new")
    new_user = _make_user("t-new", "ext-new")

    with patch("domains.tenants.service.tenant_repository") as mock_repo:
        mock_repo.get_user_by_external_id = AsyncMock(return_value=None)
        mock_repo.create_tenant_and_user = AsyncMock(return_value=(new_tenant, new_user))

        await svc.get_or_create_tenant_for_external_user(external_id="ext-new")

        call_args = mock_repo.create_tenant_and_user.call_args
        built_tenant = call_args[0][0]
        assert built_tenant.display_name == "ext-new"


@pytest.mark.asyncio
async def test_concurrent_conflict_retries_and_returns_existing():
    """Concurrent first requests: conflict is caught and existing tenant returned."""
    svc = TenantService()
    existing_tenant = _make_tenant("t-winner")
    existing_user = _make_user("t-winner", "ext-race")

    with patch("domains.tenants.service.tenant_repository") as mock_repo:
        # First lookup: user not found
        # After conflict: user found (another request won the race)
        mock_repo.get_user_by_external_id = AsyncMock(
            side_effect=[None, existing_user],
        )
        mock_repo.get_tenant = AsyncMock(return_value=existing_tenant)
        mock_repo.create_tenant_and_user = AsyncMock(
            side_effect=cosmos_exceptions.CosmosResourceExistsError(
                status_code=409,
                message="Conflict",
            ),
        )

        tenant, user = await svc.get_or_create_tenant_for_external_user("ext-race")

        assert tenant.id == "t-winner"
        assert user.external_id == "ext-race"
        # Verify: attempted creation, then retried lookup
        assert mock_repo.get_user_by_external_id.await_count == 2
        mock_repo.create_tenant_and_user.assert_awaited_once()


@pytest.mark.asyncio
async def test_conflict_without_findable_user_re_raises():
    """If conflict occurs but user still can't be found, the error propagates."""
    svc = TenantService()

    with patch("domains.tenants.service.tenant_repository") as mock_repo:
        mock_repo.get_user_by_external_id = AsyncMock(return_value=None)
        mock_repo.create_tenant_and_user = AsyncMock(
            side_effect=cosmos_exceptions.CosmosResourceExistsError(
                status_code=409,
                message="Conflict",
            ),
        )

        with pytest.raises(cosmos_exceptions.CosmosResourceExistsError):
            await svc.get_or_create_tenant_for_external_user("ext-ghost")

        # Two lookups: initial + retry after conflict
        assert mock_repo.get_user_by_external_id.await_count == 2


@pytest.mark.asyncio
async def test_batch_operation_error_triggers_retry():
    """CosmosBatchOperationError also triggers the conflict-retry path."""
    svc = TenantService()
    existing_tenant = _make_tenant("t-winner")
    existing_user = _make_user("t-winner", "ext-batch")

    with patch("domains.tenants.service.tenant_repository") as mock_repo:
        mock_repo.get_user_by_external_id = AsyncMock(
            side_effect=[None, existing_user],
        )
        mock_repo.get_tenant = AsyncMock(return_value=existing_tenant)
        mock_repo.create_tenant_and_user = AsyncMock(
            side_effect=cosmos_exceptions.CosmosBatchOperationError(
                error_index=0,
                headers={},
                status_code=409,
                message="Batch conflict",
            ),
        )

        tenant, user = await svc.get_or_create_tenant_for_external_user("ext-batch")

        assert tenant.id == "t-winner"


@pytest.mark.asyncio
async def test_create_tenant_uses_transactional_batch():
    """create_tenant (explicit) also uses transactional batch."""
    svc = TenantService()
    new_tenant = _make_tenant("t-explicit")
    new_user = _make_user("t-explicit", "ext-explicit")

    with patch("domains.tenants.service.tenant_repository") as mock_repo:
        mock_repo.create_tenant_and_user = AsyncMock(return_value=(new_tenant, new_user))

        from domains.tenants.models import CreateTenantRequest

        request = CreateTenantRequest(displayName="Explicit Tenant")
        tenant, user = await svc.create_tenant(request, "ext-explicit")

        assert tenant.id == "t-explicit"
        mock_repo.create_tenant_and_user.assert_awaited_once()
