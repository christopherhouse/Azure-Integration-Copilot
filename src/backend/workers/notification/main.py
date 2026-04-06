"""Notification worker entry point.

Runs as a standalone async process (not inside FastAPI).
Pulls terminal events from the ``notification`` subscription
and sends realtime messages via Web PubSub.
"""

from __future__ import annotations

import asyncio
import signal

import structlog

from config import settings
from shared.event_consumer import EventGridConsumer
from shared.logging import setup_logging, setup_telemetry
from shared.pubsub import PubSubService
from workers.base import BaseWorker

from .handler import NotificationHandler

SUBSCRIPTION_NAME = "notification"

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


async def main() -> None:
    setup_logging()
    setup_telemetry(service_name="integrisight-worker-notification")

    consumer = EventGridConsumer(
        endpoint=settings.event_grid_namespace_endpoint,
        namespace_topic=settings.event_grid_topic,
        subscription=SUBSCRIPTION_NAME,
    )

    pubsub = PubSubService(endpoint=settings.web_pubsub_endpoint)
    handler = NotificationHandler(pubsub_service=pubsub)

    worker = BaseWorker(consumer, handler)

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, worker.stop)

    logger.info("notification_worker_starting", subscription=SUBSCRIPTION_NAME)
    try:
        await worker.run()
    finally:
        await pubsub.close()


if __name__ == "__main__":
    asyncio.run(main())
