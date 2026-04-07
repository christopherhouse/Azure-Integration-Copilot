from collections.abc import AsyncIterator

import structlog
from azure.core.exceptions import ResourceNotFoundError
from azure.identity.aio import DefaultAzureCredential
from azure.storage.blob import ContentSettings
from azure.storage.blob.aio import BlobServiceClient

from config import settings
from shared.credential import create_credential

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

ARTIFACTS_CONTAINER = "artifacts"


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

    async def upload_blob(self, blob_path: str, data: bytes, content_type: str = "application/octet-stream") -> None:
        """Upload data to a blob at the given path in the artifacts container."""
        client = await self._get_client()
        container_client = client.get_container_client(ARTIFACTS_CONTAINER)
        blob_client = container_client.get_blob_client(blob_path)
        await blob_client.upload_blob(
            data, overwrite=True, content_settings=ContentSettings(content_type=content_type)
        )
        logger.info("blob_uploaded", blob_path=blob_path)

    async def delete_blob(self, blob_path: str) -> None:
        """Delete a blob from the artifacts container. No-op if blob does not exist."""
        client = await self._get_client()
        container_client = client.get_container_client(ARTIFACTS_CONTAINER)
        blob_client = container_client.get_blob_client(blob_path)
        try:
            await blob_client.delete_blob()
            logger.info("blob_deleted", blob_path=blob_path)
        except ResourceNotFoundError:
            logger.info("blob_already_deleted", blob_path=blob_path)
        except Exception:
            logger.warning("blob_delete_failed", blob_path=blob_path, exc_info=True)

    async def download_blob(self, blob_path: str) -> bytes:
        """Download the full contents of a blob from the artifacts container."""
        client = await self._get_client()
        container_client = client.get_container_client(ARTIFACTS_CONTAINER)
        blob_client = container_client.get_blob_client(blob_path)
        downloader = await blob_client.download_blob()
        return await downloader.readall()

    async def move_blob(self, source_path: str, dest_path: str) -> None:
        """Move a blob from *source_path* to *dest_path* (copy then delete)."""
        client = await self._get_client()
        container_client = client.get_container_client(ARTIFACTS_CONTAINER)
        source_client = container_client.get_blob_client(source_path)
        dest_client = container_client.get_blob_client(dest_path)

        # Start async copy from source to destination
        source_url = source_client.url
        await dest_client.start_copy_from_url(source_url)
        logger.info("blob_copy_started", source=source_path, dest=dest_path)

        # Delete the source blob after copy
        try:
            await source_client.delete_blob()
            logger.info("blob_moved", source=source_path, dest=dest_path)
        except ResourceNotFoundError:
            logger.info("blob_move_source_already_deleted", source=source_path)

    async def set_blob_metadata(self, blob_path: str, metadata: dict[str, str]) -> None:
        """Set custom metadata on a blob in the artifacts container."""
        client = await self._get_client()
        container_client = client.get_container_client(ARTIFACTS_CONTAINER)
        blob_client = container_client.get_blob_client(blob_path)
        await blob_client.set_blob_metadata(metadata)
        logger.info("blob_metadata_set", blob_path=blob_path, keys=list(metadata.keys()))

    async def download_blob_stream(self, blob_path: str) -> AsyncIterator[bytes]:
        """Stream blob contents as an async iterator of chunks."""
        client = await self._get_client()
        container_client = client.get_container_client(ARTIFACTS_CONTAINER)
        blob_client = container_client.get_blob_client(blob_path)
        downloader = await blob_client.download_blob()
        async for chunk in downloader.chunks():
            yield chunk

    async def ping(self) -> bool:
        """Check connectivity to Azure Blob Storage. Returns True if reachable."""
        try:
            client = await self._get_client()
            container_client = client.get_container_client(ARTIFACTS_CONTAINER)
            await container_client.get_container_properties()
            return True
        except Exception:
            logger.warning("blob_storage_ping_failed", exc_info=True)
            return False

    async def close(self) -> None:
        """Close the Blob Storage client and credential."""
        if self._client is not None:
            await self._client.close()
            self._client = None
        if self._credential is not None:
            await self._credential.close()
            self._credential = None


blob_service = BlobService()
