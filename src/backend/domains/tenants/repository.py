"""Cosmos DB repository for tenant and user documents."""

from datetime import UTC, datetime

import structlog
from azure.core import MatchConditions
from azure.cosmos import exceptions as cosmos_exceptions
from azure.cosmos.aio import ContainerProxy

from shared.cosmos import cosmos_service

from .models import Tenant, User

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

_MAX_RETRIES = 3

DATABASE_NAME = "integration-copilot"
CONTAINER_NAME = "tenants"


class TenantRepository:
    """Cosmos DB operations for the tenants container."""

    async def _get_container(self) -> ContainerProxy:
        return await cosmos_service.get_container(DATABASE_NAME, CONTAINER_NAME)

    async def create_tenant(self, tenant: Tenant) -> Tenant:
        """Create a new tenant document."""
        container = await self._get_container()
        doc = tenant.model_dump(by_alias=True, mode="json")
        result = await container.create_item(body=doc)
        logger.info("tenant_created", tenant_id=tenant.id)
        return Tenant.model_validate(result)

    async def get_tenant(self, tenant_id: str) -> Tenant | None:
        """Get a tenant by ID."""
        container = await self._get_container()
        try:
            doc = await container.read_item(item=tenant_id, partition_key=tenant_id)
            tenant = Tenant.model_validate(doc)
            tenant.etag = doc.get("_etag")
            return tenant
        except cosmos_exceptions.CosmosResourceNotFoundError:
            return None

    async def update_tenant(self, tenant: Tenant) -> Tenant:
        """Update an existing tenant document with ETag-based optimistic concurrency."""
        container = await self._get_container()
        tenant.updated_at = datetime.now(UTC)
        doc = tenant.model_dump(by_alias=True, mode="json")

        kwargs: dict = {}
        if tenant.etag:
            kwargs["etag"] = tenant.etag
            kwargs["match_condition"] = MatchConditions.IfNotModified

        result = await container.replace_item(
            item=tenant.id,
            body=doc,
            **kwargs,
        )
        logger.info("tenant_updated", tenant_id=tenant.id)
        updated = Tenant.model_validate(result)
        updated.etag = result.get("_etag")
        return updated

    async def create_user(self, user: User) -> User:
        """Create a new user document in the tenants container."""
        container = await self._get_container()
        doc = user.model_dump(by_alias=True, mode="json")
        result = await container.create_item(body=doc)
        logger.info("user_created", user_id=user.id, tenant_id=user.tenant_id)
        return User.model_validate(result)

    async def create_tenant_and_user(self, tenant: Tenant, user: User) -> tuple[Tenant, User]:
        """Atomically create a tenant and its owner user via transactional batch.

        Both documents share the same partition key (``tenant_id``), so they
        can be written in a single Cosmos DB transactional batch.  If either
        operation fails the entire batch is rolled back.
        """
        container = await self._get_container()
        tenant_doc = tenant.model_dump(by_alias=True, mode="json")
        user_doc = user.model_dump(by_alias=True, mode="json")
        batch_operations = [
            ("create", (tenant_doc,), {}),
            ("create", (user_doc,), {}),
        ]
        results = await container.execute_item_batch(
            batch_operations=batch_operations,
            partition_key=tenant.id,
        )
        if len(results) != 2:  # pragma: no cover — defensive check
            raise RuntimeError(
                f"Transactional batch returned {len(results)} results, expected 2"
            )
        # execute_item_batch returns response envelopes with statusCode,
        # requestCharge, resourceBody, etc.  Extract the actual documents.
        created_tenant = Tenant.model_validate(results[0]["resourceBody"])
        created_user = User.model_validate(results[1]["resourceBody"])
        logger.info(
            "tenant_and_user_created",
            tenant_id=tenant.id,
            user_id=user.id,
        )
        return created_tenant, created_user

    async def get_user_by_external_id(self, external_id: str) -> User | None:
        """Find a user by their external identity provider ID (cross-partition query)."""
        container = await self._get_container()
        query = "SELECT * FROM c WHERE c.type = 'user' AND c.externalId = @externalId"
        parameters = [{"name": "@externalId", "value": external_id}]
        items = container.query_items(
            query=query,
            parameters=parameters,
        )
        async for item in items:
            return User.model_validate(item)
        return None

    async def get_user(self, user_id: str, tenant_id: str) -> User | None:
        """Get a user by ID within a tenant partition."""
        container = await self._get_container()
        try:
            doc = await container.read_item(item=user_id, partition_key=tenant_id)
            if doc.get("type") != "user":
                return None
            return User.model_validate(doc)
        except cosmos_exceptions.CosmosResourceNotFoundError:
            return None

    async def update_user(self, user: User) -> User:
        """Update an existing user document."""
        container = await self._get_container()
        doc = user.model_dump(by_alias=True, mode="json")
        result = await container.replace_item(
            item=user.id,
            body=doc,
        )
        logger.info("user_updated", user_id=user.id, tenant_id=user.tenant_id)
        return User.model_validate(result)

    async def increment_usage(self, tenant_id: str, field: str, amount: int = 1) -> Tenant | None:
        """Increment a usage counter on a tenant with optimistic concurrency.

        Retries up to ``_MAX_RETRIES`` times on ETag conflicts so that
        concurrent requests don't silently lose counter updates.
        """
        for attempt in range(_MAX_RETRIES):
            tenant = await self.get_tenant(tenant_id)
            if tenant is None:
                return None

            current_value = getattr(tenant.usage, field, None)
            if current_value is None:
                logger.warning("unknown_usage_field", field=field)
                return tenant

            new_value = max(0, current_value + amount)
            setattr(tenant.usage, field, new_value)
            try:
                return await self.update_tenant(tenant)
            except cosmos_exceptions.CosmosAccessConditionFailedError:
                if attempt < _MAX_RETRIES - 1:
                    logger.info(
                        "increment_usage_retry",
                        field=field,
                        tenant_id=tenant_id,
                        attempt=attempt + 1,
                    )
                    continue
                raise

    async def reset_daily_analysis_count(self, tenant_id: str) -> Tenant | None:
        """Reset daily analysis count and update the reset timestamp."""
        tenant = await self.get_tenant(tenant_id)
        if tenant is None:
            return None

        tenant.usage.daily_analysis_count = 0
        tenant.usage.daily_analysis_reset_at = datetime.now(UTC)
        return await self.update_tenant(tenant)


tenant_repository = TenantRepository()
