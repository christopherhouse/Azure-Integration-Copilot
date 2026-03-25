import logging
import sys

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

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
    """Configure OpenTelemetry tracing with Azure Monitor export when a connection string is available."""
    resource = Resource.create({"service.name": "integration-copilot-api", "service.version": "0.1.0"})
    provider = TracerProvider(resource=resource)

    connection_string = settings.applicationinsights_connection_string
    if connection_string:
        # Use Azure Monitor exporter when connection string is configured
        from azure.monitor.opentelemetry.exporter import AzureMonitorTraceExporter

        azure_exporter = AzureMonitorTraceExporter(connection_string=connection_string)
        provider.add_span_processor(BatchSpanProcessor(azure_exporter))

    trace.set_tracer_provider(provider)


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
