import logging
import sys

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider

from config import settings

_configured = False


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


def setup_telemetry() -> None:
    """Configure OpenTelemetry with Azure Monitor export.

    When ``APPLICATIONINSIGHTS_CONNECTION_STRING`` is set, the Azure Monitor
    OpenTelemetry distro is used to configure:
    - Distributed tracing (requests, dependencies via FastAPI + httpx + aiohttp + Azure SDK)
    - Metrics (request counts, latency histograms)
    - Log export (Python stdlib logging → Azure Monitor)
    - Automatic exception recording on spans

    In local development (no connection string) a no-op tracer provider is
    configured so trace/span IDs still flow into structlog entries.
    """
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
        # - Auto-instruments FastAPI (requests), Azure SDK calls (Azure.* span
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

    # Instrument httpx (used in auth middleware for JWKS fetching) and aiohttp
    # (used in shared/events.py for Event Grid ping) so outbound HTTP calls
    # are tracked as dependency spans.
    _instrument_http_clients()


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
