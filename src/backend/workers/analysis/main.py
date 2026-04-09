"""Analysis worker entry point.

Runs as a standalone async process (not inside FastAPI).
Pulls ``AnalysisRequested`` events from the ``analysis-execution``
subscription and runs the AI agent analysis flow.
"""

from __future__ import annotations

import asyncio
import signal

import structlog

from config import settings
from domains.analysis.repository import analysis_repository
from shared.app_config import app_config_service
from shared.event_consumer import EventGridConsumer
from shared.events import event_grid_publisher
from shared.logging import setup_logging, setup_telemetry
from shared.pubsub import PubSubService
from workers.base import BaseWorker

from .agent import AgentOrchestrator
from .handler import AnalysisHandler

SUBSCRIPTION_NAME = "analysis-execution"

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def main() -> None:
    setup_logging()
    setup_telemetry(service_name="integrisight-worker-analysis")
    await app_config_service.ensure_loaded()

    consumer = EventGridConsumer(
        endpoint=settings.event_grid_namespace_endpoint,
        namespace_topic=settings.event_grid_topic,
        subscription=SUBSCRIPTION_NAME,
    )

    pubsub = PubSubService(endpoint=settings.web_pubsub_endpoint)
    orchestrator = AgentOrchestrator()

    handler = AnalysisHandler(
        analysis_repository=analysis_repository,
        event_publisher=event_grid_publisher,
        pubsub_service=pubsub,
        agent_orchestrator=orchestrator,
    )

    worker = BaseWorker(consumer, handler)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.stop)

    logger.info("analysis_worker_starting", subscription=SUBSCRIPTION_NAME)
    try:
        await worker.run()
    finally:
        await app_config_service.close()
        await orchestrator.close()
        await pubsub.close()


if __name__ == "__main__":
    asyncio.run(main())
