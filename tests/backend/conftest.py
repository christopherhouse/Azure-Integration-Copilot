import os
import sys
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

# Add the backend source directory to sys.path so that 'main' can be imported
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

# Override settings before importing the app so that no .env file is required
_test_env = {
    "ENVIRONMENT": "test",
    "COSMOS_DB_ENDPOINT": "",
    "BLOB_STORAGE_ENDPOINT": "",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "",
    "WEB_PUBSUB_ENDPOINT": "",
    "AZURE_CLIENT_ID": "",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
}
with patch.dict(os.environ, _test_env):
    from main import app  # noqa: E402
    from shared.exceptions import NotFoundError, QuotaExceededError  # noqa: E402

# Register test-only routes that raise specific exceptions so HTTP integration
# tests can verify the exception-handler pipeline produces the correct response.


@app.get("/api/v1/test/not-found")
async def _raise_not_found():
    raise NotFoundError(message="Test resource not found", detail={"id": "test-123"})


@app.get("/api/v1/test/quota-exceeded")
async def _raise_quota_exceeded():
    raise QuotaExceededError(message="Test quota exceeded", detail={"limit": "maxProjects", "current": 5, "max": 5})


@pytest_asyncio.fixture
async def client():
    """Async HTTP client wired to the FastAPI application."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

