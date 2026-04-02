"""Tests for tenant usage counter logic in TenantRepository."""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

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
    from domains.tenants.models import Tenant, TenantStatus, Usage
    from domains.tenants.repository import TenantRepository


def _make_tenant(
    tenant_id: str = "t-001",
    display_name: str = "Test Tenant",
    project_count: int = 0,
) -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id=tenant_id,
        partitionKey=tenant_id,
        displayName=display_name,
        ownerId="u-001",
        tierId="tier_free",
        status=TenantStatus.ACTIVE,
        usage=Usage(project_count=project_count, daily_analysis_reset_at=now),
        createdAt=now,
        updatedAt=now,
    )


@pytest.mark.asyncio
async def test_increment_usage_floor_prevents_negative():
    """increment_usage with negative amount clamps to 0 instead of going negative."""
    tenant_id = "t-001"
    tenant = _make_tenant(tenant_id=tenant_id, project_count=0)

    repo = TenantRepository()

    with (
        patch.object(repo, "get_tenant", new=AsyncMock(return_value=tenant)),
        patch.object(repo, "update_tenant", new=AsyncMock(side_effect=lambda t: t)),
    ):
        result = await repo.increment_usage(tenant_id, "project_count", amount=-1)

        assert result is not None
        assert result.usage.project_count == 0


@pytest.mark.asyncio
async def test_increment_usage_adds_to_current_value():
    """increment_usage correctly adds a positive amount to the current counter."""
    tenant_id = "t-001"
    tenant = _make_tenant(tenant_id=tenant_id, project_count=2)

    repo = TenantRepository()

    with (
        patch.object(repo, "get_tenant", new=AsyncMock(return_value=tenant)),
        patch.object(repo, "update_tenant", new=AsyncMock(side_effect=lambda t: t)),
    ):
        result = await repo.increment_usage(tenant_id, "project_count", amount=1)

        assert result is not None
        assert result.usage.project_count == 3


@pytest.mark.asyncio
async def test_increment_usage_returns_none_for_missing_tenant():
    """increment_usage returns None when the tenant does not exist."""
    repo = TenantRepository()

    with patch.object(repo, "get_tenant", new=AsyncMock(return_value=None)):
        result = await repo.increment_usage("t-nonexistent", "project_count", amount=1)

        assert result is None


@pytest.mark.asyncio
async def test_increment_usage_unknown_field_returns_tenant_unchanged():
    """increment_usage with an unknown field name returns the tenant without changes."""
    tenant_id = "t-001"
    tenant = _make_tenant(tenant_id=tenant_id, project_count=5)

    repo = TenantRepository()

    with patch.object(repo, "get_tenant", new=AsyncMock(return_value=tenant)):
        result = await repo.increment_usage(tenant_id, "nonexistent_field", amount=1)

        assert result is not None
        # Original project_count should be untouched
        assert result.usage.project_count == 5


@pytest.mark.asyncio
async def test_increment_usage_large_negative_clamps_to_zero():
    """increment_usage clamps to 0 even when decrement far exceeds the current value."""
    tenant_id = "t-001"
    tenant = _make_tenant(tenant_id=tenant_id, project_count=3)

    repo = TenantRepository()

    with (
        patch.object(repo, "get_tenant", new=AsyncMock(return_value=tenant)),
        patch.object(repo, "update_tenant", new=AsyncMock(side_effect=lambda t: t)),
    ):
        result = await repo.increment_usage(tenant_id, "project_count", amount=-100)

        assert result is not None
        assert result.usage.project_count == 0


@pytest.mark.asyncio
async def test_increment_usage_retries_on_etag_conflict():
    """increment_usage retries on CosmosAccessConditionFailedError and succeeds."""
    from azure.cosmos import exceptions as cosmos_exceptions

    tenant_id = "t-001"
    repo = TenantRepository()

    with (
        patch.object(
            repo,
            "get_tenant",
            new=AsyncMock(side_effect=[
                _make_tenant(tenant_id=tenant_id, project_count=2),
                _make_tenant(tenant_id=tenant_id, project_count=2),
            ]),
        ),
        patch.object(
            repo,
            "update_tenant",
            new=AsyncMock(side_effect=[
                cosmos_exceptions.CosmosAccessConditionFailedError(),
                _make_tenant(tenant_id=tenant_id, project_count=3),
            ]),
        ) as mock_update,
    ):
        result = await repo.increment_usage(tenant_id, "project_count", amount=1)

        assert result is not None
        assert result.usage.project_count == 3
        assert mock_update.call_count == 2


@pytest.mark.asyncio
async def test_increment_usage_raises_after_max_retries():
    """increment_usage raises CosmosAccessConditionFailedError after 3 failed attempts."""
    from azure.cosmos import exceptions as cosmos_exceptions

    tenant_id = "t-001"
    repo = TenantRepository()

    with (
        patch.object(
            repo,
            "get_tenant",
            new=AsyncMock(side_effect=[
                _make_tenant(tenant_id=tenant_id, project_count=2),
                _make_tenant(tenant_id=tenant_id, project_count=2),
                _make_tenant(tenant_id=tenant_id, project_count=2),
            ]),
        ),
        patch.object(
            repo,
            "update_tenant",
            new=AsyncMock(side_effect=[
                cosmos_exceptions.CosmosAccessConditionFailedError(),
                cosmos_exceptions.CosmosAccessConditionFailedError(),
                cosmos_exceptions.CosmosAccessConditionFailedError(),
            ]),
        ) as mock_update,
    ):
        with pytest.raises(cosmos_exceptions.CosmosAccessConditionFailedError):
            await repo.increment_usage(tenant_id, "project_count", amount=1)

        assert mock_update.call_count == 3
