import structlog
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob.aio import BlobServiceClient

from config import settings
from shared.credential import create_credential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


class BlobService:
    """Async wrapper around Azure Blob Storage client."""

    def __init__(self) -> None:
        self._client: BlobServiceClient | None = None
        self._credential: DefaultAzureCredential | None = None

    async def _get_client(self) -> BlobServiceClient:
        if self._client is None:
            self._credential = create_credential()
            self._client = BlobServiceClient(
                account_url=settings.blob_storage_endpoint, credential=self._credential
            )
        return self._client

    async def close(self) -> None:
        """Close the Blob Storage client and credential."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None


blob_service = BlobService()
