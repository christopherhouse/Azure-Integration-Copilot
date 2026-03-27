"""Tenant domain services — business logic for tenant management."""

import uuid
from datetime import UTC, datetime, timedelta

import structlog

from .models import (
    FREE_TIER,
    CreateTenantRequest,
    QuotaResult,
    Tenant,
    TierDefinition,
    Usage,
    User,
    UserRole,
)
from .repository import tenant_repository

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# TenantService
# ---------------------------------------------------------------------------


class TenantService:
    """Manages tenant lifecycle operations."""

    async def create_tenant(self, request: CreateTenantRequest, owner_external_id: str) -> tuple[Tenant, User]:
        """Create a new tenant and its owner user.

        Returns the created tenant and user.
        """
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        tenant = Tenant(
            id=tenant_id,
            partitionKey=tenant_id,
            displayName=request.display_name,
            ownerId=user_id,
            tierId=FREE_TIER.id,
            usage=Usage(daily_analysis_reset_at=now + timedelta(days=1)),
            createdAt=now,
            updatedAt=now,
        )
        created_tenant = await tenant_repository.create_tenant(tenant)

        user = User(
            id=user_id,
            partitionKey=tenant_id,
            tenantId=tenant_id,
            externalId=owner_external_id,
            role=UserRole.OWNER,
            createdAt=now,
        )
        created_user = await tenant_repository.create_user(user)

        logger.info(
            "tenant_registered",
            tenant_id=tenant_id,
            user_id=user_id,
        )
        return created_tenant, created_user

    async def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get a tenant by ID."""
        return await tenant_repository.get_tenant(tenant_id)

    async def update_tenant_display_name(self, tenant_id: str, display_name: str) -> Tenant | None:
        """Update a tenant's display name."""
        tenant = await tenant_repository.get_tenant(tenant_id)
        if tenant is None:
            return None
        tenant.display_name = display_name
        return await tenant_repository.update_tenant(tenant)


# ---------------------------------------------------------------------------
# UserService
# ---------------------------------------------------------------------------


class UserService:
    """Manages user lookup and creation."""

    async def get_user_by_external_id(self, external_id: str) -> User | None:
        """Look up a user by their external identity provider ID."""
        return await tenant_repository.get_user_by_external_id(external_id)


# ---------------------------------------------------------------------------
# TierService
# ---------------------------------------------------------------------------


class TierService:
    """Resolves tier definitions for tenants."""

    def get_tier(self, tier_id: str) -> TierDefinition:
        """Return the tier definition for the given tier ID.

        For MVP, always returns FREE_TIER regardless of tier_id.
        """
        return FREE_TIER


# ---------------------------------------------------------------------------
# QuotaService
# ---------------------------------------------------------------------------


class QuotaService:
    """Checks whether a tenant operation would exceed quota limits."""

    async def check(self, tenant: Tenant, tier: TierDefinition, limit_name: str) -> QuotaResult:
        """Check a specific quota limit against current tenant usage.

        Handles daily analysis reset automatically.
        """
        limits = tier.limits
        usage = tenant.usage

        # Daily analysis count auto-reset
        if limit_name == "max_daily_analyses" and datetime.now(UTC) >= usage.daily_analysis_reset_at:
            reset_tenant = await tenant_repository.reset_daily_analysis_count(tenant.id)
            if reset_tenant:
                usage = reset_tenant.usage

        limit_map: dict[str, tuple[int, int]] = {
            "max_projects": (usage.project_count, limits.max_projects),
            "max_artifacts_per_project": (usage.total_artifact_count, limits.max_artifacts_per_project),
            "max_total_artifacts": (usage.total_artifact_count, limits.max_total_artifacts),
            "max_daily_analyses": (usage.daily_analysis_count, limits.max_daily_analyses),
        }

        if limit_name not in limit_map:
            logger.warning("unknown_limit_name", limit_name=limit_name)
            return QuotaResult(allowed=True, limitName=limit_name, current=0, maximum=0)

        current, maximum = limit_map[limit_name]
        allowed = current < maximum

        return QuotaResult(
            allowed=allowed,
            limitName=limit_name,
            current=current,
            maximum=maximum,
        )


# ---------------------------------------------------------------------------
# Service singletons
# ---------------------------------------------------------------------------

tenant_service = TenantService()
user_service = UserService()
tier_service = TierService()
quota_service = QuotaService()
