"""Tenant domain models and tier definitions."""

from datetime import UTC, datetime
from enum import StrEnum

from pydantic import BaseModel, Field


class TenantStatus(StrEnum):
    """Tenant account status."""

    ACTIVE = "active"
    SUSPENDED = "suspended"


class UserStatus(StrEnum):
    """User account status."""

    ACTIVE = "active"
    DISABLED = "disabled"


class UserRole(StrEnum):
    """User roles within a tenant."""

    OWNER = "owner"


# ---------------------------------------------------------------------------
# Tier models
# ---------------------------------------------------------------------------


class TierLimits(BaseModel):
    """Numeric limits for a subscription tier."""

    max_projects: int = 3
    max_artifacts_per_project: int = 25
    max_total_artifacts: int = 50
    max_file_size_mb: int = 10
    max_daily_analyses: int = 20
    max_concurrent_analyses: int = 1
    max_graph_components_per_project: int = 500


class TierFeatures(BaseModel):
    """Feature flags for a subscription tier."""

    realtime_notifications: bool = True
    agent_analysis: bool = True
    custom_agent_prompts: bool = False
    export_graph: bool = False


class TierDefinition(BaseModel):
    """Complete tier definition combining limits and features."""

    id: str
    name: str
    slug: str
    limits: TierLimits = Field(default_factory=TierLimits)
    features: TierFeatures = Field(default_factory=TierFeatures)


# ---------------------------------------------------------------------------
# FREE_TIER constant
# ---------------------------------------------------------------------------

FREE_TIER = TierDefinition(
    id="tier_free",
    name="Free",
    slug="free",
    limits=TierLimits(),
    features=TierFeatures(),
)


# ---------------------------------------------------------------------------
# Usage tracking
# ---------------------------------------------------------------------------


class Usage(BaseModel):
    """Current usage counters for a tenant."""

    project_count: int = 0
    total_artifact_count: int = 0
    daily_analysis_count: int = 0
    daily_analysis_reset_at: datetime = Field(default_factory=lambda: datetime.now(UTC))


# ---------------------------------------------------------------------------
# Tenant and User domain models (Cosmos DB documents)
# ---------------------------------------------------------------------------


class Tenant(BaseModel):
    """Tenant document stored in Cosmos DB."""

    id: str
    partition_key: str = Field(alias="partitionKey")
    type: str = "tenant"
    display_name: str = Field(alias="displayName")
    owner_id: str = Field(alias="ownerId")
    tier_id: str = Field(default="tier_free", alias="tierId")
    status: TenantStatus = TenantStatus.ACTIVE
    usage: Usage = Field(default_factory=Usage)
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="updatedAt")
    etag: str | None = Field(default=None, alias="_etag", exclude=True)

    model_config = {"populate_by_name": True}


class User(BaseModel):
    """User document stored in Cosmos DB."""

    id: str
    partition_key: str = Field(alias="partitionKey")
    type: str = "user"
    tenant_id: str = Field(alias="tenantId")
    external_id: str = Field(alias="externalId")
    email: str = ""
    display_name: str = Field(default="", alias="displayName")
    role: UserRole = UserRole.OWNER
    status: UserStatus = UserStatus.ACTIVE
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="createdAt")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class CreateTenantRequest(BaseModel):
    """Request body for creating a new tenant."""

    display_name: str = Field(alias="displayName", min_length=1, max_length=100)

    model_config = {"populate_by_name": True}


class UpdateTenantRequest(BaseModel):
    """Request body for updating a tenant."""

    display_name: str | None = Field(default=None, alias="displayName", min_length=1, max_length=100)

    model_config = {"populate_by_name": True}


class UsageResponse(BaseModel):
    """Usage data in API responses."""

    project_count: int = Field(alias="projectCount")
    total_artifact_count: int = Field(alias="totalArtifactCount")
    daily_analysis_count: int = Field(alias="dailyAnalysisCount")
    daily_analysis_reset_at: datetime = Field(alias="dailyAnalysisResetAt")

    model_config = {"populate_by_name": True}


class TenantResponse(BaseModel):
    """Tenant data returned in API responses."""

    id: str
    display_name: str = Field(alias="displayName")
    tier_id: str = Field(alias="tierId")
    status: TenantStatus
    usage: UsageResponse
    created_at: datetime = Field(alias="createdAt")
    updated_at: datetime = Field(alias="updatedAt")

    model_config = {"populate_by_name": True}

    @classmethod
    def from_tenant(cls, tenant: Tenant) -> "TenantResponse":
        """Build a response from a Tenant domain model."""
        return cls(
            id=tenant.id,
            displayName=tenant.display_name,
            tierId=tenant.tier_id,
            status=tenant.status,
            usage=UsageResponse(
                projectCount=tenant.usage.project_count,
                totalArtifactCount=tenant.usage.total_artifact_count,
                dailyAnalysisCount=tenant.usage.daily_analysis_count,
                dailyAnalysisResetAt=tenant.usage.daily_analysis_reset_at,
            ),
            createdAt=tenant.created_at,
            updatedAt=tenant.updated_at,
        )


class QuotaResult(BaseModel):
    """Result of a quota check."""

    allowed: bool
    limit_name: str = Field(alias="limitName")
    current: int
    maximum: int

    model_config = {"populate_by_name": True}
