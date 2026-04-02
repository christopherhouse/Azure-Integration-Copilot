"""Tenant domain services — business logic for tenant management."""

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from azure.cosmos import exceptions as cosmos_exceptions

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

    def _build_tenant_and_user(
        self,
        display_name: str,
        owner_external_id: str,
        email: str = "",
        user_display_name: str = "",
    ) -> tuple[Tenant, User]:
        """Build Tenant and User model instances (no persistence)."""
        tenant_id = str(uuid.uuid4())
        user_id = str(uuid.uuid4())
        now = datetime.now(UTC)

        tenant = Tenant(
            id=tenant_id,
            partitionKey=tenant_id,
            displayName=display_name,
            ownerId=user_id,
            tierId=FREE_TIER.id,
            usage=Usage(daily_analysis_reset_at=now + timedelta(days=1)),
            createdAt=now,
            updatedAt=now,
        )
        user = User(
            id=user_id,
            partitionKey=tenant_id,
            tenantId=tenant_id,
            externalId=owner_external_id,
            email=email,
            displayName=user_display_name,
            role=UserRole.OWNER,
            createdAt=now,
        )
        return tenant, user

    async def create_tenant(self, request: CreateTenantRequest, owner_external_id: str) -> tuple[Tenant, User]:
        """Create a new tenant and its owner user.

        Uses a Cosmos DB transactional batch so both documents are created
        atomically.  Returns the created tenant and user.
        """
        tenant, user = self._build_tenant_and_user(
            display_name=request.display_name,
            owner_external_id=owner_external_id,
        )
        created_tenant, created_user = await tenant_repository.create_tenant_and_user(tenant, user)

        logger.info(
            "tenant_registered",
            tenant_id=created_tenant.id,
            user_id=created_user.id,
        )
        return created_tenant, created_user

    async def get_or_create_tenant_for_external_user(
        self,
        external_id: str,
        email: str = "",
        display_name: str = "",
    ) -> tuple[Tenant, User]:
        """Idempotent provisioning: return existing tenant or create a new one.

        1. Query user by *external_id*.
        2. If found, load and return the associated tenant.
        3. If not found, create a new tenant + owner user atomically.
        4. Handle race conditions: if a concurrent request already created the
           user, catch the conflict and return the existing tenant.
        """
        # 1. Fast path — user already provisioned
        user = await tenant_repository.get_user_by_external_id(external_id)
        if user is not None:
            tenant = await tenant_repository.get_tenant(user.tenant_id)
            if tenant is not None:
                return tenant, user
            # Orphaned user record — tenant missing. Log and fall through to
            # create a fresh tenant+user pair.
            logger.warning(
                "orphaned_user_record",
                external_id=external_id,
                tenant_id=user.tenant_id,
            )

        # 2. Derive a sensible default display name for auto-provisioned tenants
        tenant_display_name = display_name or email or external_id

        tenant, user_model = self._build_tenant_and_user(
            display_name=tenant_display_name,
            owner_external_id=external_id,
            email=email,
            user_display_name=display_name,
        )

        try:
            created_tenant, created_user = await tenant_repository.create_tenant_and_user(
                tenant, user_model
            )
            logger.info(
                "tenant_auto_provisioned",
                tenant_id=created_tenant.id,
                user_id=created_user.id,
                external_id=external_id,
            )
            return created_tenant, created_user

        except (cosmos_exceptions.CosmosResourceExistsError, cosmos_exceptions.CosmosBatchOperationError):
            # A concurrent request already created docs — retry the lookup.
            logger.info("tenant_provision_conflict_retry", external_id=external_id)
            user = await tenant_repository.get_user_by_external_id(external_id)
            if user is not None:
                tenant = await tenant_repository.get_tenant(user.tenant_id)
                if tenant is not None:
                    return tenant, user
                logger.error(
                    "conflict_retry_tenant_missing",
                    external_id=external_id,
                    tenant_id=user.tenant_id,
                )
            # If we still can't find the user after a conflict, something is
            # seriously wrong.  Let the caller handle the error.
            raise

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

    async def get_user(self, user_id: str, tenant_id: str) -> User | None:
        """Get a user by ID within a tenant."""
        return await tenant_repository.get_user(user_id, tenant_id)

    async def update_user_gravatar_email(self, user_id: str, tenant_id: str, gravatar_email: str | None) -> User | None:
        """Update a user's Gravatar email."""
        user = await tenant_repository.get_user(user_id, tenant_id)
        if user is None:
            return None
        user.gravatar_email = gravatar_email
        return await tenant_repository.update_user(user)


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
