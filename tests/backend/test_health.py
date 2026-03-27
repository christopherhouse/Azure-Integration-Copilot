import pytest


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
