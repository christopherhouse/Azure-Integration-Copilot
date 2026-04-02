"""Dead-letter handler — stores failed events to Blob Storage."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import structlog

from shared.blob import BlobService

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

DEAD_LETTER_CONTAINER = "dead-letters"


class DeadLetterHandler:
    """Persist failed events as JSON blobs for later analysis.

    Blobs are stored at::

        dead-letters/{subscription_name}/{date}/{event_id}.json
    """

    def __init__(self, blob_service: BlobService, subscription_name: str) -> None:
        self._blob = blob_service
        self._subscription_name = subscription_name

    async def store(self, event_id: str, event_data: dict, error: Exception | None = None) -> None:
        """Write a dead-letter record to Blob Storage."""
        date_str = datetime.now(UTC).strftime("%Y-%m-%d")
        blob_path = f"{DEAD_LETTER_CONTAINER}/{self._subscription_name}/{date_str}/{event_id}.json"

        payload = {
            "eventId": event_id,
            "eventData": event_data,
            "error": str(error) if error else None,
            "storedAt": datetime.now(UTC).isoformat(),
        }

        try:
            data = json.dumps(payload, default=str).encode()
            await self._blob.upload_blob(blob_path, data, content_type="application/json")
            logger.info("dead_letter_stored", blob_path=blob_path)
        except Exception:
            logger.error("dead_letter_store_failed", blob_path=blob_path, exc_info=True)
