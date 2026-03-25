import sys
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

# Add the backend source directory to sys.path so that 'main' can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

from main import app  # noqa: E402


@pytest.fixture
async def client():
    """Async HTTP client wired to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
