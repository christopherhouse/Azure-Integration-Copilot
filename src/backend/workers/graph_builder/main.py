"""Graph builder worker entry point.

Runs as a standalone async process (not inside FastAPI).
Pulls ``ArtifactParsed`` events from the ``graph-builder``
subscription and builds graph data from parse results.
"""

from __future__ import annotations

import asyncio
import signal

import structlog

from config import settings
from domains.artifacts.repository import artifact_repository
from domains.graph.repository import graph_repository
from domains.projects.repository import project_repository
from shared.cosmos import cosmos_service
from shared.event_consumer import EventGridConsumer
from shared.events import event_grid_publisher
from shared.logging import setup_logging
from workers.base import BaseWorker
from workers.graph_builder.handler import GraphBuilderHandler

SUBSCRIPTION_NAME = "graph-builder"

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def main() -> None:
    setup_logging()

    consumer = EventGridConsumer(
        endpoint=settings.event_grid_namespace_endpoint,
        namespace_topic=settings.event_grid_topic,
        subscription=SUBSCRIPTION_NAME,
    )

    handler = GraphBuilderHandler(
        artifact_repository=artifact_repository,
        graph_repository=graph_repository,
        project_repository=project_repository,
        cosmos_service=cosmos_service,
        event_publisher=event_grid_publisher,
    )

    worker = BaseWorker(consumer, handler)

    # Graceful shutdown on SIGTERM / SIGINT
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.stop)

    logger.info("graph_builder_worker_starting", subscription=SUBSCRIPTION_NAME)
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
