"""Tests for backend observability / OpenTelemetry setup."""

import logging
import os
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

# Fake Application Insights connection string used across tests.
_FAKE_CONNECTION_STRING = (
    "InstrumentationKey=00000000-0000-0000-0000-000000000000;"
    "IngestionEndpoint=https://eastus.in.applicationinsights.azure.com/"
)


# ---------------------------------------------------------------------------
# setup_telemetry — no connection string (local dev / test)
# ---------------------------------------------------------------------------


def test_setup_telemetry_no_connection_string_sets_provider():
    """setup_telemetry() installs a TracerProvider even without a connection string."""
    from opentelemetry import trace

    from shared import logging as app_logging

    # Reset module-level state so we can call setup_telemetry() cleanly.
    app_logging._configured = False
    app_logging._telemetry_configured = False

    with patch.dict(os.environ, {"APPLICATIONINSIGHTS_CONNECTION_STRING": ""}):
        # Re-import settings with the patched environment
        import importlib

        import config

        importlib.reload(config)
        app_logging.settings = config.settings

        app_logging.setup_telemetry()

    provider = trace.get_tracer_provider()
    # Should be a real (non-proxy) provider after setup
    assert provider is not None


def test_setup_telemetry_with_connection_string_calls_configure_azure_monitor():
    """setup_telemetry() calls configure_azure_monitor() when a connection string is set."""
    import importlib

    import config
    import shared.logging as app_logging

    mock_configure = MagicMock()

    with (
        patch.dict(os.environ, {"APPLICATIONINSIGHTS_CONNECTION_STRING": _FAKE_CONNECTION_STRING}),
        patch("azure.monitor.opentelemetry.configure_azure_monitor", mock_configure),
    ):
        importlib.reload(config)
        app_logging.settings = config.settings
        app_logging._telemetry_configured = False

        app_logging.setup_telemetry()

    mock_configure.assert_called_once()
    call_kwargs = mock_configure.call_args.kwargs
    assert call_kwargs["connection_string"] == _FAKE_CONNECTION_STRING


def test_setup_telemetry_instruments_app_instance():
    """setup_telemetry(app) calls FastAPIInstrumentor.instrument_app(app) for correlation."""
    import importlib

    import config
    import shared.logging as app_logging

    mock_app = MagicMock()
    mock_instrument_app = MagicMock()

    with (
        patch.dict(os.environ, {"APPLICATIONINSIGHTS_CONNECTION_STRING": ""}),
        patch(
            "opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app",
            mock_instrument_app,
        ),
    ):
        importlib.reload(config)
        app_logging.settings = config.settings
        app_logging._telemetry_configured = False

        app_logging.setup_telemetry(app=mock_app)

    mock_instrument_app.assert_called_once_with(mock_app)


def test_setup_telemetry_without_app_skips_instrument_app():
    """setup_telemetry() without app parameter does not call instrument_app."""
    import importlib

    import config
    import shared.logging as app_logging

    mock_instrument_app = MagicMock()

    with (
        patch.dict(os.environ, {"APPLICATIONINSIGHTS_CONNECTION_STRING": ""}),
        patch(
            "opentelemetry.instrumentation.fastapi.FastAPIInstrumentor.instrument_app",
            mock_instrument_app,
        ),
    ):
        importlib.reload(config)
        app_logging.settings = config.settings
        app_logging._telemetry_configured = False

        app_logging.setup_telemetry()

    mock_instrument_app.assert_not_called()


def test_setup_telemetry_instruments_httpx_client():
    """setup_telemetry() instruments the httpx client for outbound dependency tracking."""
    from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

    import shared.logging as app_logging

    # Uninstrument first to get a clean state
    try:
        HTTPXClientInstrumentor().uninstrument()
    except Exception:
        pass

    with patch.dict(os.environ, {"APPLICATIONINSIGHTS_CONNECTION_STRING": ""}):
        app_logging._instrument_http_clients()

    assert HTTPXClientInstrumentor().is_instrumented_by_opentelemetry


def test_setup_telemetry_instruments_aiohttp_client():
    """setup_telemetry() instruments the aiohttp client for outbound dependency tracking."""
    from opentelemetry.instrumentation.aiohttp_client import AioHttpClientInstrumentor

    import shared.logging as app_logging

    try:
        AioHttpClientInstrumentor().uninstrument()
    except Exception:
        pass

    app_logging._instrument_http_clients()

    assert AioHttpClientInstrumentor().is_instrumented_by_opentelemetry


# ---------------------------------------------------------------------------
# Exception recording on spans
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_app_error_5xx_records_exception_on_span():
    """AppError with status >= 500 records the exception and sets span status to ERROR."""
    from opentelemetry.trace import StatusCode

    from main import app_error_handler
    from shared.exceptions import AppError

    err = AppError(status_code=500, code="TEST_ERROR", message="test server error")
    mock_request = MagicMock()
    mock_request.headers.get.return_value = "test-req-id"

    mock_span = MagicMock()

    with patch("main.trace.get_current_span", return_value=mock_span):
        await app_error_handler(mock_request, err)

    mock_span.record_exception.assert_called_once_with(err)
    mock_span.set_status.assert_called_once_with(StatusCode.ERROR, err.message)


@pytest.mark.asyncio
async def test_app_error_4xx_does_not_record_error_on_span():
    """AppError with status < 500 does NOT mark the span as ERROR."""
    from main import app_error_handler
    from shared.exceptions import NotFoundError

    err = NotFoundError(message="not found")
    mock_request = MagicMock()
    mock_request.headers.get.return_value = "test-req-id"

    mock_span = MagicMock()

    with patch("main.trace.get_current_span", return_value=mock_span):
        await app_error_handler(mock_request, err)

    mock_span.record_exception.assert_not_called()
    mock_span.set_status.assert_not_called()


@pytest.mark.asyncio
async def test_unhandled_exception_handler_records_exception_on_span():
    """Unhandled exceptions record the exception and set span status to ERROR."""
    from opentelemetry.trace import StatusCode

    from main import unhandled_exception_handler

    err = RuntimeError("unexpected")
    mock_request = MagicMock()
    mock_request.headers.get.return_value = "test-req-id"
    mock_request.url.path = "/api/v1/test"

    mock_span = MagicMock()
    # The structlog processor _add_opentelemetry_context calls
    # format(ctx.trace_id, "032x"), so provide real int values.
    mock_span.get_span_context.return_value.trace_id = 0x1234567890ABCDEF
    mock_span.get_span_context.return_value.span_id = 0xFEDCBA09

    with patch("main.trace.get_current_span", return_value=mock_span):
        response = await unhandled_exception_handler(mock_request, err)

    assert response.status_code == 500
    mock_span.record_exception.assert_called_once_with(err)
    mock_span.set_status.assert_called_once_with(StatusCode.ERROR, str(err))


@pytest.mark.asyncio
async def test_server_error_route_returns_500(client):
    """The /api/v1/test/server-error route returns a standard 500 ErrorResponse."""
    response = await client.get("/api/v1/test/server-error")
    assert response.status_code == 500
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "TEST_SERVER_ERROR"
    assert "request_id" in body["error"]


@pytest.mark.asyncio
async def test_unhandled_exception_route_returns_500():
    """An unhandled RuntimeError returns a standard 500 INTERNAL_SERVER_ERROR response.

    Uses raise_app_exceptions=False so that the underlying ExceptionGroup raised
    by Starlette's BaseHTTPMiddleware task group does not propagate to the test client.
    The response content is still verified for correctness.
    """
    from httpx import ASGITransport, AsyncClient

    from main import app as _app

    transport = ASGITransport(app=_app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        response = await c.get("/api/v1/test/unhandled-error")

    assert response.status_code == 500
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "INTERNAL_SERVER_ERROR"
    assert "request_id" in body["error"]


# ---------------------------------------------------------------------------
# Logging setup
# ---------------------------------------------------------------------------


def test_setup_logging_configures_root_logger():
    """setup_logging() attaches a StreamHandler to the root logger."""
    import shared.logging as app_logging

    # Reset configured flag
    app_logging._configured = False

    app_logging.setup_logging()

    root = logging.getLogger()
    handler_types = [type(h).__name__ for h in root.handlers]
    assert "StreamHandler" in handler_types


def test_setup_logging_suppresses_noisy_loggers():
    """setup_logging() sets azure/opentelemetry/urllib3 loggers to WARNING."""
    import shared.logging as app_logging

    app_logging._configured = False
    app_logging.setup_logging()

    for name in ("azure", "opentelemetry", "urllib3"):
        assert logging.getLogger(name).level == logging.WARNING


def test_setup_logging_idempotent():
    """Calling setup_logging() twice does not add duplicate handlers."""
    import shared.logging as app_logging

    app_logging._configured = False
    app_logging.setup_logging()
    handler_count = len(logging.getLogger().handlers)

    app_logging.setup_logging()
    assert len(logging.getLogger().handlers) == handler_count


# ---------------------------------------------------------------------------
# HealthCheckHeadFilter — span filtering
# ---------------------------------------------------------------------------


def _make_mock_span(*, kind, method, path, trace_id=1):
    """Create a mock span with the given HTTP attributes."""
    span = MagicMock()
    span.kind = kind
    span.context.trace_id = trace_id
    span.attributes = {
        "http.request.method": method,
        "url.path": path,
    }
    return span


def test_head_health_span_is_filtered():
    """HEAD /api/v1/health server spans are not forwarded to the wrapped processor."""
    from opentelemetry.trace import SpanKind

    from shared.logging import HealthCheckHeadFilter

    mock_next = MagicMock()
    f = HealthCheckHeadFilter(mock_next)

    span = _make_mock_span(kind=SpanKind.SERVER, method="HEAD", path="/api/v1/health")
    f.on_start(span)
    f.on_end(span)

    mock_next.on_start.assert_called_once_with(span, None)
    mock_next.on_end.assert_not_called()


def test_head_health_ready_span_is_filtered():
    """HEAD /api/v1/health/ready server spans are also filtered."""
    from opentelemetry.trace import SpanKind

    from shared.logging import HealthCheckHeadFilter

    mock_next = MagicMock()
    f = HealthCheckHeadFilter(mock_next)

    span = _make_mock_span(kind=SpanKind.SERVER, method="HEAD", path="/api/v1/health/ready")
    f.on_start(span)
    f.on_end(span)

    mock_next.on_end.assert_not_called()


def test_get_health_span_is_not_filtered():
    """GET /api/v1/health server spans are forwarded normally."""
    from opentelemetry.trace import SpanKind

    from shared.logging import HealthCheckHeadFilter

    mock_next = MagicMock()
    f = HealthCheckHeadFilter(mock_next)

    span = _make_mock_span(kind=SpanKind.SERVER, method="GET", path="/api/v1/health")
    f.on_start(span)
    f.on_end(span)

    mock_next.on_end.assert_called_once_with(span)


def test_head_non_health_span_is_not_filtered():
    """HEAD requests to non-health endpoints are forwarded normally."""
    from opentelemetry.trace import SpanKind

    from shared.logging import HealthCheckHeadFilter

    mock_next = MagicMock()
    f = HealthCheckHeadFilter(mock_next)

    span = _make_mock_span(kind=SpanKind.SERVER, method="HEAD", path="/api/v1/projects")
    f.on_start(span)
    f.on_end(span)

    mock_next.on_end.assert_called_once_with(span)


def test_child_spans_of_filtered_trace_are_also_filtered():
    """Dependency spans sharing a trace_id with a filtered HEAD health span are dropped."""
    from opentelemetry.trace import SpanKind

    from shared.logging import HealthCheckHeadFilter

    mock_next = MagicMock()
    f = HealthCheckHeadFilter(mock_next)

    # Parent HEAD health check — filtered
    parent = _make_mock_span(kind=SpanKind.SERVER, method="HEAD", path="/api/v1/health", trace_id=42)
    f.on_start(parent)

    # Child dependency span (e.g. Cosmos DB ping) — same trace_id, different attributes
    child = MagicMock()
    child.kind = SpanKind.CLIENT
    child.context.trace_id = 42
    child.attributes = {"db.system": "cosmosdb", "db.operation.name": "ReadItem"}
    f.on_start(child)
    f.on_end(child)  # child ends before parent

    # Parent ends
    f.on_end(parent)

    mock_next.on_end.assert_not_called()


def test_unrelated_spans_not_affected_by_filter():
    """Spans with a different trace_id are forwarded even when filter is active."""
    from opentelemetry.trace import SpanKind

    from shared.logging import HealthCheckHeadFilter

    mock_next = MagicMock()
    f = HealthCheckHeadFilter(mock_next)

    # Filtered HEAD health
    filtered = _make_mock_span(kind=SpanKind.SERVER, method="HEAD", path="/api/v1/health", trace_id=1)
    f.on_start(filtered)

    # Unrelated request on different trace
    normal = _make_mock_span(kind=SpanKind.SERVER, method="GET", path="/api/v1/projects", trace_id=2)
    f.on_start(normal)
    f.on_end(normal)

    mock_next.on_end.assert_called_once_with(normal)


def test_filter_shutdown_delegates():
    """shutdown() is forwarded to the wrapped processor."""
    from shared.logging import HealthCheckHeadFilter

    mock_next = MagicMock()
    f = HealthCheckHeadFilter(mock_next)
    f.shutdown()
    mock_next.shutdown.assert_called_once()


def test_filter_force_flush_delegates():
    """force_flush() is forwarded to the wrapped processor."""
    from shared.logging import HealthCheckHeadFilter

    mock_next = MagicMock()
    f = HealthCheckHeadFilter(mock_next)
    f.force_flush(5000)
    mock_next.force_flush.assert_called_once_with(5000)


def test_filter_uses_old_semconv_attributes():
    """The filter also checks legacy OTel HTTP semantic convention attribute names."""
    from opentelemetry.trace import SpanKind

    from shared.logging import HealthCheckHeadFilter

    mock_next = MagicMock()
    f = HealthCheckHeadFilter(mock_next)

    # Use old-style attribute names
    span = MagicMock()
    span.kind = SpanKind.SERVER
    span.context.trace_id = 99
    span.attributes = {"http.method": "HEAD", "http.target": "/api/v1/health"}

    f.on_start(span)
    f.on_end(span)

    mock_next.on_end.assert_not_called()


def test_filter_bounded_memory():
    """The suppressed trace set does not grow beyond _MAX_TRACKED entries."""
    from opentelemetry.trace import SpanKind

    from shared.logging import HealthCheckHeadFilter

    mock_next = MagicMock()
    f = HealthCheckHeadFilter(mock_next)
    f._MAX_TRACKED = 5  # small limit for testing

    for i in range(10):
        span = _make_mock_span(kind=SpanKind.SERVER, method="HEAD", path="/api/v1/health", trace_id=i)
        f.on_start(span)

    assert len(f._suppressed_traces) == 5
    # Only the last 5 trace_ids should be retained
    assert list(f._suppressed_traces.keys()) == [5, 6, 7, 8, 9]


# ---------------------------------------------------------------------------
# _install_health_head_filter — integration with real TracerProvider
# ---------------------------------------------------------------------------


def test_install_filter_wraps_active_span_processor():
    """_install_health_head_filter() wraps the active span processor with the filter."""
    from opentelemetry import trace as trace_api
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import SimpleSpanProcessor, SpanExporter, SpanExportResult
    from opentelemetry.trace import SpanKind

    import shared.logging as app_logging

    class _MemExporter(SpanExporter):
        def __init__(self):
            self.spans = []

        def export(self, spans):
            self.spans.extend(spans)
            return SpanExportResult.SUCCESS

        def shutdown(self):
            pass

    exporter = _MemExporter()
    provider = TracerProvider()
    provider.add_span_processor(SimpleSpanProcessor(exporter))

    with patch.object(trace_api, "get_tracer_provider", return_value=provider):
        app_logging._install_health_head_filter()

    # The active span processor should now be our filter
    assert type(provider._active_span_processor).__name__ == "HealthCheckHeadFilter"

    # Tracer created AFTER installation picks up the filter
    tracer = provider.get_tracer("integration-test")

    # HEAD health check span should be dropped
    with tracer.start_as_current_span(
        "HEAD /api/v1/health",
        kind=SpanKind.SERVER,
        attributes={"http.method": "HEAD", "http.target": "/api/v1/health"},
    ):
        pass
    assert len(exporter.spans) == 0, "HEAD health check span should be suppressed"

    # GET health check span should pass through
    with tracer.start_as_current_span(
        "GET /api/v1/health",
        kind=SpanKind.SERVER,
        attributes={"http.method": "GET", "http.target": "/api/v1/health"},
    ):
        pass
    assert len(exporter.spans) == 1, "GET health check span should be exported"

    # Normal API span should pass through
    with tracer.start_as_current_span(
        "GET /api/v1/projects",
        kind=SpanKind.SERVER,
        attributes={"http.method": "GET", "http.target": "/api/v1/projects"},
    ):
        pass
    assert len(exporter.spans) == 2, "Normal API span should be exported"
    assert [s.name for s in exporter.spans] == [
        "GET /api/v1/health",
        "GET /api/v1/projects",
    ]


def test_install_filter_logs_success(caplog):
    """_install_health_head_filter() logs an info message on success."""
    from opentelemetry import trace as trace_api
    from opentelemetry.sdk.trace import TracerProvider

    import shared.logging as app_logging

    provider = TracerProvider()

    with (
        patch.object(trace_api, "get_tracer_provider", return_value=provider),
        caplog.at_level(logging.INFO),
    ):
        app_logging._install_health_head_filter()

    assert any("health_head_filter_installed" in r.message for r in caplog.records)


def test_install_filter_logs_warning_for_noop_provider(caplog):
    """_install_health_head_filter() logs a warning when the provider is not SDK type."""
    from opentelemetry import trace as trace_api
    from opentelemetry.trace import NoOpTracerProvider

    import shared.logging as app_logging

    provider = NoOpTracerProvider()

    with (
        patch.object(trace_api, "get_tracer_provider", return_value=provider),
        caplog.at_level(logging.WARNING),
    ):
        app_logging._install_health_head_filter()

    assert any("health_head_filter_skipped" in r.message for r in caplog.records)
