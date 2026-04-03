import sys
from pathlib import Path

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
