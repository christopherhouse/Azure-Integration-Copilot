"""Worker base class with async pull loop, idempotency, and error handling."""

from __future__ import annotations

import asyncio
from abc import ABC, abstractmethod
from typing import Any

import structlog
from opentelemetry import metrics, trace
from opentelemetry.context import attach, detach
from opentelemetry.propagate import extract
from opentelemetry.trace import StatusCode

from shared.event_consumer import EventGridConsumer

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

tracer = trace.get_tracer(__name__)
meter = metrics.get_meter(__name__)

# -- OTel metrics instruments ------------------------------------------------
_poll_counter = meter.create_counter(
    "worker.poll.iterations",
    description="Total number of poll-loop iterations",
)
_messages_received = meter.create_counter(
    "worker.messages.received",
    description="Total number of messages received from Event Grid",
)
_messages_processed = meter.create_counter(
    "worker.messages.processed",
    description="Total number of messages successfully processed",
)
_messages_failed = meter.create_counter(
    "worker.messages.failed",
    description="Total number of messages that failed processing",
)
_empty_polls = meter.create_counter(
    "worker.poll.empty",
    description="Total number of poll iterations that returned no messages",
)


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

    @property
    def accepted_event_types(self) -> frozenset[str] | None:
        """Return the set of CloudEvent types this handler can process.

        If ``None`` (the default), all event types are accepted.  Override
        this in subclasses so that the :class:`BaseWorker` can discard
        events delivered by misconfigured subscriptions instead of crashing.
        """
        return None

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
        self._handler_name = type(handler).__name__

    async def run(self) -> None:
        """Main pull loop — runs until :meth:`stop` is called."""
        attrs = {"worker.handler": self._handler_name}
        logger.info("worker_started", handler=self._handler_name)
        poll_iteration = 0
        try:
            while self._running:
                poll_iteration += 1
                iter_attrs = {**attrs, "worker.poll.iteration": poll_iteration}
                _poll_counter.add(1, iter_attrs)

                with tracer.start_as_current_span(
                    "worker poll",
                    attributes=iter_attrs,
                ) as span:
                    try:
                        details = await self._consumer.receive_events()
                    except asyncio.CancelledError:
                        if not self._running:
                            span.set_status(StatusCode.OK)
                            break
                        logger.warning("receive_cancelled")
                        span.set_status(StatusCode.OK)
                        continue
                    except Exception as exc:
                        logger.error("receive_events_failed", exc_info=True)
                        span.set_status(StatusCode.ERROR, "receive_events_failed")
                        span.record_exception(exc)
                        await asyncio.sleep(self._poll_interval)
                        continue

                    message_count = len(details) if details else 0
                    span.set_attribute("worker.messages.count", message_count)

                    if not details:
                        _empty_polls.add(1, iter_attrs)
                        span.set_status(StatusCode.OK)
                        logger.debug(
                            "poll_empty",
                            handler=self._handler_name,
                            iteration=poll_iteration,
                        )
                        await asyncio.sleep(self._poll_interval)
                        continue

                    _messages_received.add(message_count, iter_attrs)
                    logger.info(
                        "poll_received",
                        handler=self._handler_name,
                        iteration=poll_iteration,
                        message_count=message_count,
                    )

                    for detail in details:
                        await self._process_event(detail)

                    span.set_status(StatusCode.OK)
        except asyncio.CancelledError:
            logger.info("worker_cancelled", was_running=self._running)
        finally:
            await self._consumer.close()
            logger.info(
                "worker_stopped",
                handler=self._handler_name,
                total_iterations=poll_iteration,
            )

    def stop(self) -> None:
        """Signal the pull loop to exit after the current iteration."""
        logger.info("worker_stop_requested")
        self._running = False

    async def _process_event(self, detail: Any) -> None:
        """Validate, de-duplicate, and hand off a single event.

        **Distributed Tracing:**
        If the CloudEvent contains W3C Trace Context extension attributes
        (``traceparent``, ``tracestate``), they are extracted and used as the
        parent context for the worker processing span. This allows the worker
        trace to continue from the API request that published the event,
        maintaining end-to-end correlation across the event-driven pipeline.
        """
        event = detail.event
        lock_token = detail.broker_properties.lock_token
        event_id = getattr(event, "id", "unknown")
        event_data: dict[str, Any] = event.data or {}
        tenant_id = event_data.get("tenantId")

        log = logger.bind(event_id=event_id, event_type=event.type, tenant_id=tenant_id)
        span_attrs = {
            "worker.handler": self._handler_name,
            "worker.event.id": event_id,
            "worker.event.type": str(event.type),
        }

        # Extract W3C Trace Context from CloudEvent extensions (if present).
        # The API publishes events with 'traceparent' and 'tracestate' extension
        # attributes. We extract these into an OpenTelemetry context so that the
        # worker span becomes a child of the original API request span.
        carrier = {}
        if hasattr(event, "extensions") and event.extensions:
            carrier = {k: v for k, v in event.extensions.items() if k in ("traceparent", "tracestate")}

        parent_ctx = extract(carrier) if carrier else None
        token = attach(parent_ctx) if parent_ctx else None

        try:
            with tracer.start_as_current_span(
                "worker process event",
                attributes=span_attrs,
            ) as span:
                handler_attrs = {"worker.handler": self._handler_name}

                # --- Tenant validation ---
                if not tenant_id:
                    log.error("missing_tenant_id")
                    span.set_status(StatusCode.ERROR, "missing_tenant_id")
                    await self._consumer.acknowledge([lock_token])
                    return

                span.set_attribute("worker.tenant.id", tenant_id)

                # --- Event type validation ---
                accepted = self._handler.accepted_event_types
                if accepted is not None and str(event.type) not in accepted:
                    log.warning(
                        "unexpected_event_type",
                        accepted_types=sorted(accepted),
                    )
                    span.set_status(StatusCode.OK)
                    await self._consumer.acknowledge([lock_token])
                    return

                # --- Idempotency check ---
                try:
                    if await self._handler.is_already_processed(event_data):
                        log.info("event_already_processed")
                        span.set_status(StatusCode.OK)
                        await self._consumer.acknowledge([lock_token])
                        return
                except Exception:
                    log.error("idempotency_check_failed", exc_info=True)
                    span.set_status(StatusCode.ERROR, "idempotency_check_failed")
                    _messages_failed.add(1, handler_attrs)
                    await self._consumer.release([lock_token])
                    return

                # --- Process ---
                try:
                    log.info("event_processing_started")
                    await self._handler.handle(event_data)
                    await self._consumer.acknowledge([lock_token])
                    log.info("event_processing_succeeded")
                    span.set_status(StatusCode.OK)
                    _messages_processed.add(1, handler_attrs)

                except TransientError:
                    log.warning("transient_error", exc_info=True)
                    span.set_status(StatusCode.ERROR, "transient_error")
                    _messages_failed.add(1, handler_attrs)
                    await self._consumer.release([lock_token])

                except PermanentError as exc:
                    log.error("permanent_error", exc_info=True)
                    span.set_status(StatusCode.ERROR, "permanent_error")
                    _messages_failed.add(1, handler_attrs)
                    try:
                        await self._handler.handle_failure(event_data, exc)
                    except Exception:
                        log.error("handle_failure_callback_error", exc_info=True)
                    await self._consumer.acknowledge([lock_token])

                except Exception:
                    log.error("unexpected_error", exc_info=True)
                    span.set_status(StatusCode.ERROR, "unexpected_error")
                    _messages_failed.add(1, handler_attrs)
                    await self._consumer.release([lock_token])
        finally:
            if token is not None:
                detach(token)
