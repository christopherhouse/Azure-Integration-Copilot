import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

from shared.exceptions import (  # noqa: E402
    AppError,
    ForbiddenError,
    NotFoundError,
    QuotaExceededError,
    UnauthorizedError,
    ValidationError,
)


# ---------------------------------------------------------------------------
# Exception class unit tests
# ---------------------------------------------------------------------------

def test_not_found_error_defaults():
    """NotFoundError has correct status code and error code."""
    err = NotFoundError()
    assert err.status_code == 404
    assert err.code == "RESOURCE_NOT_FOUND"


def test_quota_exceeded_error_defaults():
    """QuotaExceededError has correct status code and error code."""
    err = QuotaExceededError()
    assert err.status_code == 429
    assert err.code == "QUOTA_EXCEEDED"


def test_validation_error_defaults():
    """ValidationError has correct status code and error code."""
    err = ValidationError()
    assert err.status_code == 422
    assert err.code == "VALIDATION_ERROR"


def test_forbidden_error_defaults():
    """ForbiddenError has correct status code and error code."""
    err = ForbiddenError()
    assert err.status_code == 403
    assert err.code == "FORBIDDEN"


def test_unauthorized_error_defaults():
    """UnauthorizedError has correct status code and error code."""
    err = UnauthorizedError()
    assert err.status_code == 401
    assert err.code == "UNAUTHORIZED"


def test_app_error_custom_fields():
    """AppError accepts custom status_code, code, message, and detail."""
    err = AppError(status_code=418, code="TEAPOT", message="I am a teapot", detail={"brew": "earl grey"})
    assert err.status_code == 418
    assert err.code == "TEAPOT"
    assert err.message == "I am a teapot"
    assert err.detail == {"brew": "earl grey"}


def test_not_found_error_custom_message():
    """NotFoundError can accept a custom message."""
    err = NotFoundError(message="Project not found", detail={"id": "prj_123"})
    assert err.message == "Project not found"
    assert err.detail == {"id": "prj_123"}


# ---------------------------------------------------------------------------
# HTTP integration tests — errors via the FastAPI exception handler
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_404_error_response_format(client):
    """404 responses follow the standard ErrorResponse format."""
    response = await client.get("/api/v1/does-not-exist")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    error = body["error"]
    assert error["code"] == "RESOURCE_NOT_FOUND"
    assert "message" in error
    assert "request_id" in error


@pytest.mark.asyncio
async def test_error_response_includes_request_id_header(client):
    """Error responses use the X-Request-ID header when provided."""
    custom_id = "err-test-id-456"
    response = await client.get(
        "/api/v1/does-not-exist",
        headers={"X-Request-ID": custom_id},
    )
    assert response.status_code == 404
    body = response.json()
    assert body["error"]["request_id"] == custom_id


# ---------------------------------------------------------------------------
# HTTP integration tests — AppError subclasses raised in handlers
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_not_found_error_returns_404_via_handler(client):
    """Raising NotFoundError in a handler returns 404 with the standard error format."""
    response = await client.get("/api/v1/test/not-found")
    assert response.status_code == 404
    body = response.json()
    assert "error" in body
    error = body["error"]
    assert error["code"] == "RESOURCE_NOT_FOUND"
    assert error["message"] == "Test resource not found"
    assert error["detail"] == {"id": "test-123"}
    assert "request_id" in error


@pytest.mark.asyncio
async def test_quota_exceeded_error_returns_429_via_handler(client):
    """Raising QuotaExceededError in a handler returns 429 with the standard error format."""
    response = await client.get("/api/v1/test/quota-exceeded")
    assert response.status_code == 429
    body = response.json()
    assert "error" in body
    error = body["error"]
    assert error["code"] == "QUOTA_EXCEEDED"
    assert error["message"] == "Test quota exceeded"
    assert error["detail"] == {"limit": "maxProjects", "current": 5, "max": 5}
    assert "request_id" in error
