"""Worker base class with async pull loop, idempotency, and error handling."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import structlog

from shared.event_consumer import EventGridConsumer

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)


# ---------------------------------------------------------------------------
# Error hierarchy for worker processing
# ---------------------------------------------------------------------------


class TransientError(Exception):
    """Indicates a transient failure; the event should be released for retry."""


class PermanentError(Exception):
    """Indicates a permanent failure; the event should be acknowledged after
    calling the handler's ``handle_failure`` callback."""


# ---------------------------------------------------------------------------
# Handler protocol
# ---------------------------------------------------------------------------


class WorkerHandler(ABC):
    """Interface that each domain-specific worker handler must implement."""

    @abstractmethod
    async def is_already_processed(self, event_data: dict[str, Any]) -> bool:
        """Return ``True`` if the event has already been handled (idempotency)."""

    @abstractmethod
    async def handle(self, event_data: dict[str, Any]) -> None:
        """Process the event.

        Raise :class:`TransientError` for retriable failures or
        :class:`PermanentError` for non-retriable failures.
        """

    @abstractmethod
    async def handle_failure(self, event_data: dict[str, Any], error: Exception) -> None:
        """Called when a :class:`PermanentError` is raised during processing."""


# ---------------------------------------------------------------------------
# Base worker
# ---------------------------------------------------------------------------


class BaseWorker:
    """Async pull-loop worker that receives events from Event Grid Namespace.

    Parameters
    ----------
    consumer:
        An :class:`EventGridConsumer` bound to the correct topic/subscription.
    handler:
        A :class:`WorkerHandler` that implements the domain logic.
    poll_interval:
        Seconds to wait between receive calls when no events are returned.
    """

    def __init__(
        self,
        consumer: EventGridConsumer,
        handler: WorkerHandler,
        *,
        poll_interval: float = 5.0,
    ) -> None:
        self._consumer = consumer
        self._handler = handler
        self._poll_interval = poll_interval
        self._running = True

    async def run(self) -> None:
        """Main pull loop — runs until :meth:`stop` is called."""
        logger.info("worker_started", handler=type(self._handler).__name__)
        try:
            while self._running:
                try:
                    details = await self._consumer.receive_events()
                except Exception:
                    logger.error("receive_events_failed", exc_info=True)
                    await asyncio.sleep(self._poll_interval)
                    continue

                if not details:
                    await asyncio.sleep(self._poll_interval)
                    continue

                for detail in details:
                    await self._process_event(detail)
        finally:
            await self._consumer.close()
            logger.info("worker_stopped")

    def stop(self) -> None:
        """Signal the pull loop to exit after the current iteration."""
        self._running = False

    async def _process_event(self, detail: Any) -> None:
        """Validate, de-duplicate, and hand off a single event."""
        event = detail.event
        lock_token = detail.broker_properties.lock_token
        event_id = getattr(event, "id", "unknown")
        event_data: dict[str, Any] = event.data or {}
        tenant_id = event_data.get("tenantId")

        log = logger.bind(event_id=event_id, event_type=event.type, tenant_id=tenant_id)

        # --- Tenant validation ---
        if not tenant_id:
            log.error("missing_tenant_id")
            await self._consumer.acknowledge([lock_token])
            return

        # --- Idempotency check ---
        try:
            if await self._handler.is_already_processed(event_data):
                log.info("event_already_processed")
                await self._consumer.acknowledge([lock_token])
                return
        except Exception:
            log.error("idempotency_check_failed", exc_info=True)
            await self._consumer.release([lock_token])
            return

        # --- Process ---
        try:
            log.info("event_processing_started")
            await self._handler.handle(event_data)
            await self._consumer.acknowledge([lock_token])
            log.info("event_processing_succeeded")

        except TransientError:
            log.warning("transient_error", exc_info=True)
            await self._consumer.release([lock_token])

        except PermanentError as exc:
            log.error("permanent_error", exc_info=True)
            try:
                await self._handler.handle_failure(event_data, exc)
            except Exception:
                log.error("handle_failure_callback_error", exc_info=True)
            await self._consumer.acknowledge([lock_token])

        except Exception:
            log.error("unexpected_error", exc_info=True)
            await self._consumer.release([lock_token])
