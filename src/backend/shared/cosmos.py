from typing import Any

import structlog
from azure.cosmos.aio import ContainerProxy, CosmosClient
from azure.identity.aio import DefaultAzureCredential
from opentelemetry import trace

from config import settings
from shared.credential import create_credential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


def _enrich_span_with_request_charge(response: Any) -> None:
    """Capture Cosmos DB RU cost from response headers and add to the current OTel span.

    The ``x-ms-request-charge`` header is present on every Cosmos DB response
    and contains the Request Unit (RU) cost of the operation.  This mirrors the
    ``db.cosmosdb.request_charge`` attribute that the .NET and Java Azure Cosmos
    DB SDKs emit natively but that the Python SDK does not yet include.

    This function is intended to be used as a ``raw_response_hook`` on the
    :class:`~azure.cosmos.aio.CosmosClient`, where it is invoked by the
    azure-core ``CustomHookPolicy`` while the SDK's distributed-tracing span
    is still active and recording.
    """
    try:
        request_charge = response.http_response.headers.get("x-ms-request-charge")
        if request_charge is not None:
            span = trace.get_current_span()
            if span.is_recording():
                span.set_attribute("db.cosmosdb.request_charge", float(request_charge))
    except Exception:  # noqa: BLE001
        # Telemetry enrichment must never break the request pipeline.
        pass


class CosmosService:
    """Async wrapper around Azure Cosmos DB client."""

    def __init__(self) -> None:
        self._client: CosmosClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> CosmosClient:
        if self._client is None:
            self._credential = create_credential()
            self._client = CosmosClient(
                url=settings.cosmos_db_endpoint,
                credential=self._credential,
                raw_response_hook=_enrich_span_with_request_charge,
            )
        return self._client

    async def get_container(self, database_name: str, container_name: str) -> ContainerProxy:
        """Get a Cosmos DB container client."""
        client = await self._get_client()
        database = client.get_database_client(database_name)
        return database.get_container_client(container_name)

    async def ping(self) -> bool:
        """Check connectivity to Cosmos DB. Returns True if reachable."""
        try:
            client = await self._get_client()
            # List databases as a connectivity check
            async for _ in client.list_databases():
                break
            return True
        except Exception:
            logger.warning("cosmos_ping_failed", exc_info=True)
            return False

    async def close(self) -> None:
        """Close the Cosmos DB client and credential."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None


cosmos_service = CosmosService()
