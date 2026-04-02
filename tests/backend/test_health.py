import re
from unittest.mock import AsyncMock, patch

import pytest

from main import _compute_health_status
from shared.models import ResourceStatus as RS

# Expected resource types returned by the health endpoint
EXPECTED_RESOURCE_TYPES = {"database", "object_storage", "broker", "messaging"}


@pytest.mark.asyncio
async def test_health_returns_failed_when_all_unavailable(client):
    """GET /api/v1/health returns status 'failed' when all dependencies are unavailable."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "failed"
    assert "meta" in body
    assert "request_id" in body["meta"]
    assert "timestamp" in body["meta"]


@pytest.mark.asyncio
async def test_health_response_content_type(client):
    """GET /api/v1/health returns JSON content type."""
    response = await client.get("/api/v1/health")
    assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_nonexistent_route_returns_404(client):
    """Requesting an undefined route returns 404 with standard error format."""
    response = await client.get("/api/v1/nonexistent")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "RESOURCE_NOT_FOUND"
    assert "message" in body["error"]
    assert "request_id" in body["error"]


@pytest.mark.asyncio
async def test_health_method_not_allowed(client):
    """POST to the health endpoint returns 405 Method Not Allowed."""
    response = await client.post("/api/v1/health")
    assert response.status_code == 405


@pytest.mark.asyncio
async def test_health_ready_returns_503_when_not_configured(client):
    """GET /api/v1/health/ready returns 503 when Cosmos DB is not configured."""
    response = await client.get("/api/v1/health/ready")
    assert response.status_code == 503
    body = response.json()
    assert "error" in body
    assert body["error"]["code"] == "SERVICE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_health_ready_route_registered(client):
    """The /api/v1/health/ready route is registered in the app."""
    response = await client.get("/api/v1/health/ready")
    # Should return 503 (not 404), confirming the route is registered
    assert response.status_code != 404


@pytest.mark.asyncio
async def test_health_sets_request_id(client):
    """Health endpoint respects a provided X-Request-ID header."""
    custom_id = "test-request-id-123"
    response = await client.get("/api/v1/health", headers={"X-Request-ID": custom_id})
    assert response.status_code == 200
    body = response.json()
    assert body["meta"]["request_id"] == custom_id


@pytest.mark.asyncio
async def test_health_head_returns_200(client):
    """HEAD /api/v1/health returns 200 without calling downstream dependencies."""
    response = await client.head("/api/v1/health")
    assert response.status_code == 200
    # HEAD should return a simple 200 with no resource headers — container
    # orchestrators only need a status code, and skipping dependency checks
    # avoids telemetry noise and unnecessary load.
    assert "x-resource-database-available" not in response.headers
    assert "x-health-duration" not in response.headers


# ---------------------------------------------------------------------------
# Resource-level health checks (GET)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_get_includes_resources_array(client):
    """GET /api/v1/health returns data.resources as a list."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert "resources" in body["data"]
    assert isinstance(body["data"]["resources"], list)


@pytest.mark.asyncio
async def test_health_get_resources_contain_expected_types(client):
    """Resources include database, object_storage, broker, messaging."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    resources = response.json()["data"]["resources"]
    returned_types = {r["type"] for r in resources}
    assert returned_types == EXPECTED_RESOURCE_TYPES


@pytest.mark.asyncio
async def test_health_get_resources_structure(client):
    """Each resource has 'type' (str) and 'available' (bool) keys."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    resources = response.json()["data"]["resources"]
    assert len(resources) > 0, "Expected at least one resource"
    for resource in resources:
        assert "type" in resource, f"Missing 'type' key in resource: {resource}"
        assert "available" in resource, f"Missing 'available' key in resource: {resource}"
        assert isinstance(resource["type"], str)
        assert isinstance(resource["available"], bool)


@pytest.mark.asyncio
async def test_health_get_database_unavailable_when_not_configured(client):
    """database resource shows available=False and no latency when Cosmos DB endpoint is not configured."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    resources = response.json()["data"]["resources"]
    db_resource = next(r for r in resources if r["type"] == "database")
    assert db_resource["available"] is False
    assert "latency" not in db_resource


@pytest.mark.asyncio
async def test_health_get_all_resources_unavailable_when_not_configured(client):
    """All resources show available=False when endpoints are empty."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    resources = response.json()["data"]["resources"]
    for resource in resources:
        assert resource["available"] is False, (
            f"Expected {resource['type']} to be unavailable when endpoint is not configured"
        )


@pytest.mark.asyncio
async def test_health_get_includes_duration(client):
    """GET /api/v1/health returns data.duration matching 'X.X ms' format."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert "duration" in body["data"], "Expected 'duration' key in data"
    assert re.match(r"^\d+\.\d+ ms$", body["data"]["duration"]), (
        f"Duration format unexpected: {body['data']['duration']}"
    )


# ---------------------------------------------------------------------------
# Mocked Cosmos DB available (GET)
# ---------------------------------------------------------------------------

_FAKE_COSMOS_ENDPOINT = "https://fake-cosmos.documents.azure.com:443/"


@pytest.fixture()
def mock_cosmos_available():
    """Patch cosmos_service.ping to succeed and settings to have a valid endpoint."""
    with (
        patch("main.cosmos_service.ping", new_callable=AsyncMock, return_value=True),
        patch("main.settings.cosmos_db_endpoint", _FAKE_COSMOS_ENDPOINT),
    ):
        yield


@pytest.mark.asyncio
async def test_health_get_database_available_with_latency(client, mock_cosmos_available):
    """When Cosmos DB is reachable, database resource shows available=True with latency."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    resources = response.json()["data"]["resources"]
    db_resource = next(r for r in resources if r["type"] == "database")
    assert db_resource["available"] is True
    assert "latency" in db_resource
    assert re.match(r"^\d+\.\d+ ms$", db_resource["latency"]), (
        f"Latency format unexpected: {db_resource['latency']}"
    )


# ---------------------------------------------------------------------------
# Mocked Blob Storage available (GET)
# ---------------------------------------------------------------------------

_FAKE_BLOB_ENDPOINT = "https://fakestorage.blob.core.windows.net/"


@pytest.fixture()
def mock_blob_available():
    """Patch blob_service.ping to succeed and settings to have a valid endpoint."""
    with (
        patch("main.blob_service.ping", new_callable=AsyncMock, return_value=True),
        patch("main.settings.blob_storage_endpoint", _FAKE_BLOB_ENDPOINT),
    ):
        yield


@pytest.mark.asyncio
async def test_health_get_blob_available_with_latency(client, mock_blob_available):
    """When Blob Storage is reachable, object_storage resource shows available=True with latency."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    resources = response.json()["data"]["resources"]
    blob_resource = next(r for r in resources if r["type"] == "object_storage")
    assert blob_resource["available"] is True
    assert "latency" in blob_resource
    assert re.match(r"^\d+\.\d+ ms$", blob_resource["latency"])


# ---------------------------------------------------------------------------
# Mocked Event Grid available (GET)
# ---------------------------------------------------------------------------

_FAKE_EVENT_GRID_ENDPOINT = "https://fake-eventgrid.westus2-1.eventgrid.azure.net/"


@pytest.fixture()
def mock_event_grid_available():
    """Patch event_grid_publisher.ping to succeed and settings to have a valid endpoint."""
    with (
        patch("main.event_grid_publisher.ping", new_callable=AsyncMock, return_value=True),
        patch("main.settings.event_grid_namespace_endpoint", _FAKE_EVENT_GRID_ENDPOINT),
    ):
        yield


@pytest.mark.asyncio
async def test_health_get_event_grid_available_with_latency(client, mock_event_grid_available):
    """When Event Grid is reachable, broker resource shows available=True with latency."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    resources = response.json()["data"]["resources"]
    eg_resource = next(r for r in resources if r["type"] == "broker")
    assert eg_resource["available"] is True
    assert "latency" in eg_resource
    assert re.match(r"^\d+\.\d+ ms$", eg_resource["latency"])


# ---------------------------------------------------------------------------
# Mocked Web PubSub available (GET)
# ---------------------------------------------------------------------------

_FAKE_WEB_PUBSUB_ENDPOINT = "https://fake-webpubsub.webpubsub.azure.com/"


@pytest.fixture()
def mock_web_pubsub_available():
    """Patch web_pubsub_service.ping to succeed and settings to have a valid endpoint."""
    with (
        patch("main.web_pubsub_service.ping", new_callable=AsyncMock, return_value=True),
        patch("main.settings.web_pubsub_endpoint", _FAKE_WEB_PUBSUB_ENDPOINT),
    ):
        yield


@pytest.mark.asyncio
async def test_health_get_web_pubsub_available_with_latency(client, mock_web_pubsub_available):
    """When Web PubSub is reachable, messaging resource shows available=True with latency."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    resources = response.json()["data"]["resources"]
    wps_resource = next(r for r in resources if r["type"] == "messaging")
    assert wps_resource["available"] is True
    assert "latency" in wps_resource
    assert re.match(r"^\d+\.\d+ ms$", wps_resource["latency"])


# ---------------------------------------------------------------------------
# All resources available
# ---------------------------------------------------------------------------


@pytest.fixture()
def mock_all_resources_available(
    mock_cosmos_available,
    mock_blob_available,
    mock_event_grid_available,
    mock_web_pubsub_available,
):
    """Composite fixture: all four downstream dependencies are reachable."""
    yield


@pytest.mark.asyncio
async def test_health_get_all_resources_available(client, mock_all_resources_available):
    """When all dependencies are reachable, every resource shows available=True with latency."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    resources = response.json()["data"]["resources"]
    for resource in resources:
        assert resource["available"] is True, (
            f"Expected {resource['type']} to be available"
        )
        assert "latency" in resource, (
            f"Expected latency for {resource['type']}"
        )
        assert re.match(r"^\d+\.\d+ ms$", resource["latency"])


@pytest.mark.asyncio
async def test_health_status_ok_when_all_available(client, mock_all_resources_available):
    """GET /api/v1/health returns status 'ok' when all dependencies are available."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "ok"


# ---------------------------------------------------------------------------
# Degraded status (some dependencies available)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_status_degraded_when_some_available(client, mock_cosmos_available):
    """GET /api/v1/health returns status 'degraded' when only some dependencies are available."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json()["data"]["status"] == "degraded"


# ---------------------------------------------------------------------------
# _compute_health_status unit tests
# ---------------------------------------------------------------------------


def test_compute_health_status_ok():
    """Returns 'ok' when all resources are available."""
    resources = [RS(type="database", available=True), RS(type="broker", available=True)]
    assert _compute_health_status(resources) == "ok"


def test_compute_health_status_failed():
    """Returns 'failed' when no resources are available."""
    resources = [RS(type="database", available=False), RS(type="broker", available=False)]
    assert _compute_health_status(resources) == "failed"


def test_compute_health_status_degraded():
    """Returns 'degraded' when some but not all resources are available."""
    resources = [RS(type="database", available=True), RS(type="broker", available=False)]
    assert _compute_health_status(resources) == "degraded"


def test_compute_health_status_empty():
    """Returns 'failed' when resource list is empty."""
    assert _compute_health_status([]) == "failed"
