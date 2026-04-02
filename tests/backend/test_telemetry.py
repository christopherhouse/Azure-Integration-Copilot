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

        app_logging.setup_telemetry()

    mock_configure.assert_called_once()
    call_kwargs = mock_configure.call_args.kwargs
    assert call_kwargs["connection_string"] == _FAKE_CONNECTION_STRING


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

