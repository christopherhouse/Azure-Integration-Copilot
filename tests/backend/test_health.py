import re
from unittest.mock import AsyncMock, patch

import pytest


# Expected resource types returned by the health endpoint
EXPECTED_RESOURCE_TYPES = {"database", "object_storage", "broker", "messaging"}


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    """GET /api/v1/health returns 200 with enveloped status ok."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    body = response.json()
    assert body["data"]["status"] == "ok"
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
    """HEAD /api/v1/health returns 200 (used by AFD health probes)."""
    response = await client.head("/api/v1/health")
    assert response.status_code == 200


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
async def test_health_get_scaffolded_resources_unavailable(client):
    """object_storage, broker, and messaging are all available=False."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    resources = response.json()["data"]["resources"]
    scaffolded_types = {"object_storage", "broker", "messaging"}
    for resource in resources:
        if resource["type"] in scaffolded_types:
            assert resource["available"] is False, (
                f"Expected {resource['type']} to be unavailable"
            )


# ---------------------------------------------------------------------------
# Resource-level health checks (HEAD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_head_returns_resource_headers(client):
    """HEAD returns X-Resource-*-Available headers for all 4 resource types."""
    response = await client.head("/api/v1/health")
    assert response.status_code == 200
    expected_headers = [
        "x-resource-database-available",
        "x-resource-object-storage-available",
        "x-resource-broker-available",
        "x-resource-messaging-available",
    ]
    for header in expected_headers:
        assert header in response.headers, f"Missing header: {header}"
        assert response.headers[header] in ("true", "false")


@pytest.mark.asyncio
async def test_health_head_no_latency_header_when_unavailable(client):
    """HEAD does not include X-Resource-*-Latency headers when resource is unavailable."""
    response = await client.head("/api/v1/health")
    assert response.status_code == 200
    latency_headers = [
        key for key in response.headers if key.lower().endswith("-latency")
    ]
    assert latency_headers == [], (
        f"Expected no latency headers when all resources are unavailable, "
        f"but found: {latency_headers}"
    )


# ---------------------------------------------------------------------------
# Mocked Cosmos DB available (GET and HEAD)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_health_get_database_available_with_latency(client):
    """When Cosmos DB is reachable, database resource shows available=True with latency."""
    with (
        patch("main.cosmos_service.ping", new_callable=AsyncMock, return_value=True),
        patch("main.settings.cosmos_db_endpoint", "https://fake-cosmos.documents.azure.com:443/"),
    ):
        response = await client.get("/api/v1/health")
    assert response.status_code == 200
    resources = response.json()["data"]["resources"]
    db_resource = next(r for r in resources if r["type"] == "database")
    assert db_resource["available"] is True
    assert "latency" in db_resource
    assert re.match(r"^\d+\.\d+ ms$", db_resource["latency"]), (
        f"Latency format unexpected: {db_resource['latency']}"
    )


@pytest.mark.asyncio
async def test_health_head_database_latency_header_when_available(client):
    """When Cosmos DB is reachable, HEAD includes X-Resource-Database-Latency header."""
    with (
        patch("main.cosmos_service.ping", new_callable=AsyncMock, return_value=True),
        patch("main.settings.cosmos_db_endpoint", "https://fake-cosmos.documents.azure.com:443/"),
    ):
        response = await client.head("/api/v1/health")
    assert response.status_code == 200
    assert "x-resource-database-available" in response.headers
    assert response.headers["x-resource-database-available"] == "true"
    assert "x-resource-database-latency" in response.headers
    latency_value = response.headers["x-resource-database-latency"]
    assert re.match(r"^\d+\.\d+ ms$", latency_value), (
        f"Latency header format unexpected: {latency_value}"
    )
