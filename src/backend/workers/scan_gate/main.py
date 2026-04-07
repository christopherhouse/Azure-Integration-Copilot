"""Scan-gate worker entry point.

Runs as a standalone async process (not inside FastAPI).
Pulls ``ArtifactUploaded`` events from the ``malware-scan-gate``
subscription and scans artifacts with ClamAV before allowing them
to proceed with processing.
"""

from __future__ import annotations

import asyncio
import signal

import structlog

from config import settings
from domains.artifacts.repository import artifact_repository
from shared.blob import blob_service
from shared.clamav import clamav_scanner
from shared.event_consumer import EventGridConsumer
from shared.events import event_grid_publisher
from shared.logging import setup_logging, setup_telemetry
from workers.base import BaseWorker
from workers.scan_gate.handler import ScanGateHandler

SUBSCRIPTION_NAME = "malware-scan-gate"

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def main() -> None:
    setup_logging()
    setup_telemetry(service_name="integrisight-worker-scan-gate")

    consumer = EventGridConsumer(
        endpoint=settings.event_grid_namespace_endpoint,
        namespace_topic=settings.event_grid_topic,
        subscription=SUBSCRIPTION_NAME,
    )

    handler = ScanGateHandler(
        artifact_repository=artifact_repository,
        event_publisher=event_grid_publisher,
        blob_service=blob_service,
        clamav_scanner=clamav_scanner,
    )

    worker = BaseWorker(consumer, handler)

    # Graceful shutdown on SIGTERM / SIGINT
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.stop)

    logger.info("scan_gate_worker_starting", subscription=SUBSCRIPTION_NAME)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
