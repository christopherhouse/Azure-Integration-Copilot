import logging
import sys
import threading
from collections import OrderedDict

import structlog
from opentelemetry import trace
from opentelemetry.context import Context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, Span, SpanProcessor, TracerProvider
from opentelemetry.trace import SpanKind

from config import settings

_configured = False
_telemetry_configured = False


# ---------------------------------------------------------------------------
# Span filtering — suppress HEAD health-check noise
# ---------------------------------------------------------------------------


class HealthCheckHeadFilter(SpanProcessor):
    """Drop all telemetry for HEAD requests to health-check endpoints.

    Container orchestrators (Azure Container Apps, Kubernetes) issue frequent
    HEAD probes to ``/api/v1/health``.  These create significant noise in
    Application Insights without adding diagnostic value.  GET requests to the
    same endpoints are still traced normally.

    The filter works in two phases:

    1. **on_start** — when a ``SERVER`` span starts with
       ``http.request.method == HEAD`` and a health-check path, its
       ``trace_id`` is recorded in a bounded set.
    2. **on_end** — any span whose ``trace_id`` is in that set is silently
       dropped (not forwarded to the wrapped processor), which prevents both
       the request span *and* its child dependency spans from being exported.
    """

    _MAX_TRACKED: int = 1_000

    def __init__(self, next_processor: SpanProcessor) -> None:
        self._next = next_processor
        self._suppressed_traces: OrderedDict[int, bool] = OrderedDict()
        self._lock = threading.Lock()

    # -- SpanProcessor interface ---------------------------------------------

    def on_start(self, span: Span, parent_context: Context | None = None) -> None:
        if self._is_head_health_check(span):
            with self._lock:
                self._suppressed_traces[span.context.trace_id] = True
                # Evict oldest entries to bound memory usage.
                while len(self._suppressed_traces) > self._MAX_TRACKED:
                    self._suppressed_traces.popitem(last=False)
        self._next.on_start(span, parent_context)

    def on_end(self, span: ReadableSpan) -> None:
        with self._lock:
            if span.context.trace_id in self._suppressed_traces:
                return  # silently drop — don't forward to exporter
        self._next.on_end(span)

    def shutdown(self) -> None:
        self._next.shutdown()

    def force_flush(self, timeout_millis: int = 30_000) -> bool:
        return self._next.force_flush(timeout_millis)

    # -- helpers -------------------------------------------------------------

    @staticmethod
    def _is_head_health_check(span: Span) -> bool:
        """Return *True* for SERVER spans created by HEAD /api/v1/health* requests."""
        if span.kind != SpanKind.SERVER:
            return False
        attrs = span.attributes or {}
        method = attrs.get("http.request.method") or attrs.get("http.method", "")
        path = attrs.get("url.path") or attrs.get("http.target", "")
        return method == "HEAD" and path.startswith("/api/v1/health")


# ---------------------------------------------------------------------------
# OpenTelemetry context injection for structured logging
# ---------------------------------------------------------------------------


def _add_opentelemetry_context(
    _logger: logging.Logger, _method_name: str, event_dict: dict
) -> dict:
    """Structlog processor that injects OpenTelemetry trace/span IDs into log entries."""
    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx and ctx.trace_id:
        event_dict["trace_id"] = format(ctx.trace_id, "032x")
        event_dict["span_id"] = format(ctx.span_id, "016x")
    return event_dict


# ---------------------------------------------------------------------------
# Telemetry bootstrap
# ---------------------------------------------------------------------------


def setup_telemetry(app=None) -> None:
    """Configure OpenTelemetry with Azure Monitor export.

    **Must be called at module level** — before any ASGI events are processed.
    Starlette builds the middleware stack on the first ASGI scope (the lifespan
    event), so calling this inside a lifespan handler is too late:
    ``instrument_app`` replaces ``build_middleware_stack`` but the original has
    already been called and cached.

    Args:
        app: The FastAPI application instance.  When provided the app is
            explicitly instrumented with ``FastAPIInstrumentor.instrument_app``
            so that incoming requests produce server spans.  This is required
            because ``configure_azure_monitor`` only patches the FastAPI
            *class* — it does **not** retroactively instrument app instances
            that were created before it was called.

    When ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set, the Azure Monitor
    OpenTelemetry distro is used to configure:
    - Distributed tracing (requests, dependencies via FastAPI + httpx + aiohttp + Azure SDK)
    - Metrics (request counts, latency histograms)
    - Log export (Python stdlib logging → Azure Monitor)
    - Automatic exception recording on spans

    In local development (no connection string) a no-op tracer provider is
    configured so trace/span IDs still flow into structlog entries.
    """
    global _telemetry_configured  # noqa: PLW0603
    if _telemetry_configured:
        return
    _telemetry_configured = True

    resource = Resource.create(
        {
            "service.name": "integration-copilot-api",
            "service.version": "0.1.0",
        }
    )

    connection_string = settings.applicationinsights_connection_string
    if connection_string:
        # Use the Azure Monitor OpenTelemetry distro. This single call:
        # - Exports traces, metrics, and logs to Azure Monitor Application Insights
        # - Auto-instruments the FastAPI *class*, Azure SDK calls (Azure.* span
        #   sources), and Python stdlib logging
        # - Applies BatchSpanProcessor so export is non-blocking
        from azure.monitor.opentelemetry import configure_azure_monitor

        configure_azure_monitor(
            connection_string=connection_string,
            resource=resource,
            # logger_name="" attaches log export to the root stdlib logger so
            # all application log records are forwarded to Azure Monitor.
            # The "azure", "opentelemetry", and "urllib3" loggers are clamped
            # to WARNING in setup_logging() before this is called, preventing
            # the recursive-export loop described in the Azure Monitor docs.
            logger_name="",
        )
    else:
        # No connection string — local dev / test.  Set up a minimal provider
        # so that trace/span IDs are still injected into structlog entries.
        provider = TracerProvider(resource=resource)
        trace.set_tracer_provider(provider)

    # Install the HEAD health-check filter BEFORE instrumenting the app or
    # HTTP clients.  ``instrument_app`` and the HTTP-client instrumentors
    # obtain a tracer whose ``_span_processor`` is captured from
    # ``provider._active_span_processor`` at creation time.  By installing
    # the filter first, every tracer created afterwards already routes spans
    # through the filter, ensuring both request *and* dependency spans for
    # HEAD health-check probes are suppressed.
    _install_health_head_filter()

    # Explicitly instrument the *existing* app instance so that incoming
    # requests produce server spans.  configure_azure_monitor() only patches
    # the FastAPI class; instances created before that call are missed.
    # Without this, dependency spans (Azure SDK, httpx, aiohttp) have no
    # parent request span and appear uncorrelated in Application Insights.
    if app is not None:
        _instrument_app(app)

    # Instrument httpx (used in auth middleware for JWKS fetching) and aiohttp
    # (used in shared/events.py for Event Grid ping) so outbound HTTP calls
    # are tracked as dependency spans.
    _instrument_http_clients()


def _instrument_app(app) -> None:  # noqa: ANN001
    """Explicitly instrument an existing FastAPI app instance.

    ``configure_azure_monitor()`` calls ``FastAPIInstrumentor.instrument()``
    which replaces the ``FastAPI`` *class* with an instrumented subclass.
    Instances that already exist are **not** affected.  This helper calls
    ``instrument_app()`` which patches the specific instance's
    ``build_middleware_stack`` so that the ``OpenTelemetryMiddleware`` is
    inserted into the ASGI pipeline.  The middleware creates server spans for
    every incoming HTTP request, providing the parent context that dependency
    spans need for end-to-end correlation in Application Insights.
    """
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
    except Exception:  # noqa: BLE001
        # If instrumentation fails (e.g. unexpected version mismatch), log and
        # continue — the app should still work, just without request spans.
        structlog.get_logger(__name__).warning(
            "fastapi_instrument_app_failed",
            msg="Could not instrument FastAPI app instance; request-dependency correlation may be degraded.",
        )


def _instrument_http_clients() -> None:
    """Instrument httpx and aiohttp clients for outbound dependency tracking."""
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
    except ImportError:
        pass

    try:
        from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor

        AioHttpClientInstrumentor().instrument()
    except ImportError:
        pass


def _install_health_head_filter() -> None:
    """Wrap the active span processor with :class:`HealthCheckHeadFilter`.

    The filter intercepts ``on_end`` calls and silently drops spans that
    belong to HEAD health-check requests, preventing them from being exported
    to Application Insights.

    This function accesses the ``_active_span_processor`` private attribute of
    the SDK ``TracerProvider``.  While private, this is the standard community
    pattern for injecting span-level filtering into an existing OTel pipeline.
    """
    from opentelemetry.sdk.trace import TracerProvider as SdkTracerProvider

    provider = trace.get_tracer_provider()
    if isinstance(provider, SdkTracerProvider) and hasattr(provider, "_active_span_processor"):
        original = provider._active_span_processor
        provider._active_span_processor = HealthCheckHeadFilter(original)


def setup_logging() -> None:
    """Configure structlog with JSON output in production and colored console in development.

    Integrates OpenTelemetry trace context into all log entries.
    """
    global _configured  # noqa: PLW0603
    if _configured:
        return
    _configured = True

    is_production = settings.environment.lower() in ("production", "prod")

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        _add_opentelemetry_context,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_production:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(logging.INFO)

    # Reduce noise from Azure SDK and OpenTelemetry loggers
    for noisy_logger in ("azure", "opentelemetry", "urllib3"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)
