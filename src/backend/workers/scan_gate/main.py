"""Scan-gate worker entry point.

Runs as a standalone async process (not inside FastAPI).
Pulls ``ArtifactUploaded`` events from the ``malware-scan-gate``
subscription and transitions artifacts through the scan stage.
"""

from __future__ import annotations

import asyncio
import signal

import structlog

from config import settings
from domains.artifacts.repository import artifact_repository
from shared.event_consumer import EventGridConsumer
from shared.events import event_grid_publisher
from shared.logging import setup_logging
from workers.base import BaseWorker
from workers.scan_gate.handler import ScanGateHandler

SUBSCRIPTION_NAME = "malware-scan-gate"

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def main() -> None:
    setup_logging()

    consumer = EventGridConsumer(
        endpoint=settings.event_grid_namespace_endpoint,
        namespace_topic=settings.event_grid_topic,
        subscription=SUBSCRIPTION_NAME,
    )

    handler = ScanGateHandler(
        artifact_repository=artifact_repository,
        event_publisher=event_grid_publisher,
        defender_enabled=settings.defender_scan_enabled,
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
