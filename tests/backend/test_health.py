import pytest


@pytest.mark.asyncio
async def test_health_returns_ok(client):
    """GET /api/v1/health returns 200 with status ok."""
    response = await client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.asyncio
async def test_health_response_content_type(client):
    """GET /api/v1/health returns JSON content type."""
    response = await client.get("/api/v1/health")
    assert response.headers["content-type"] == "application/json"


@pytest.mark.asyncio
async def test_nonexistent_route_returns_404(client):
    """Requesting an undefined route returns 404."""
    response = await client.get("/api/v1/nonexistent")
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_health_method_not_allowed(client):
    """POST to the health endpoint returns 405 Method Not Allowed."""
    response = await client.post("/api/v1/health")
    assert response.status_code == 405
