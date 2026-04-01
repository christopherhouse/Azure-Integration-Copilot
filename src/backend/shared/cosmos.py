import structlog
from azure.cosmos.aio import ContainerProxy, CosmosClient
from azure.identity.aio import DefaultAzureCredential

from config import settings
from shared.credential import create_credential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class CosmosService:
    """Async wrapper around Azure Cosmos DB client."""

    def __init__(self) -> None:
        self._client: CosmosClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> CosmosClient:
        if self._client is None:
            self._credential = create_credential()
            self._client = CosmosClient(url=settings.cosmos_db_endpoint, credential=self._credential)
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
