import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

from main import app  # noqa: E402


def test_app_title():
    """FastAPI app title matches the project name."""
    assert app.title == "Integrisight.ai API"


def test_app_version():
    """FastAPI app version is set."""
    assert app.version == "0.1.0"


def test_health_route_registered():
    """The /api/v1/health route is registered in the app."""
    routes = [route.path for route in app.routes]
    assert "/api/v1/health" in routes


def test_health_ready_route_registered():
    """The /api/v1/health/ready route is registered in the app."""
    routes = [route.path for route in app.routes]
    assert "/api/v1/health/ready" in routes


@pytest.mark.asyncio
async def test_cors_headers_in_preflight_response():
    """CORS preflight includes X-Trace-ID, traceparent, and tracestate in allowed headers."""
    from config import settings

    # Only test CORS if it's configured
    if not settings.cors_allowed_origins:
        pytest.skip("CORS not configured")

    client = TestClient(app)
    origin = settings.cors_allowed_origins.split(",")[0].strip()

    response = client.options(
        "/api/v1/health",
        headers={
            "Origin": origin,
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "X-Trace-ID, traceparent, tracestate",
        },
    )

    # Verify preflight succeeds
    assert response.status_code == 200

    # Verify CORS headers are present
    assert "access-control-allow-headers" in response.headers
    allowed_headers = response.headers["access-control-allow-headers"].lower()

    # Verify new trace headers are allowed
    assert "x-trace-id" in allowed_headers
    assert "traceparent" in allowed_headers
    assert "tracestate" in allowed_headers

    # Verify existing headers are still allowed
    assert "content-type" in allowed_headers
    assert "authorization" in allowed_headers
    assert "x-request-id" in allowed_headers
