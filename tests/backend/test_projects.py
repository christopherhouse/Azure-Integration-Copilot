"""Tests for project CRUD endpoints."""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src" / "backend"))

_test_env = {
    "ENVIRONMENT": "test",
    "COSMOS_DB_ENDPOINT": "https://fake-cosmos.documents.azure.com:443/",
    "BLOB_STORAGE_ENDPOINT": "",
    "EVENT_GRID_NAMESPACE_ENDPOINT": "",
    "WEB_PUBSUB_ENDPOINT": "",
    "AZURE_CLIENT_ID": "",
    "APPLICATIONINSIGHTS_CONNECTION_STRING": "",
    "SKIP_AUTH": "true",
}

with patch.dict(os.environ, _test_env):
    from main import app  # noqa: E402

from domains.projects.models import Project, ProjectStatus
from domains.tenants.models import Tenant, TenantStatus, Usage, User, UserRole, UserStatus


def _make_tenant(tenant_id: str = "t-001", display_name: str = "Test Tenant") -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id=tenant_id,
        partitionKey=tenant_id,
        displayName=display_name,
        ownerId="u-001",
        tierId="tier_free",
        status=TenantStatus.ACTIVE,
        usage=Usage(daily_analysis_reset_at=now),
        createdAt=now,
        updatedAt=now,
    )


def _make_user(tenant_id: str = "t-001", external_id: str = "dev-user-001") -> User:
    return User(
        id="u-001",
        partitionKey=tenant_id,
        tenantId=tenant_id,
        externalId=external_id,
        role=UserRole.OWNER,
        status=UserStatus.ACTIVE,
        createdAt=datetime.now(UTC),
    )


def _make_project(
    project_id: str = "prj-001",
    tenant_id: str = "t-001",
    name: str = "Test Project",
    description: str | None = None,
    status: ProjectStatus = ProjectStatus.ACTIVE,
) -> Project:
    now = datetime.now(UTC)
    return Project(
        id=project_id,
        partitionKey=tenant_id,
        tenantId=tenant_id,
        name=name,
        description=description,
        status=status,
        createdBy="u-001",
        createdAt=now,
        updatedAt=now,
    )


def _setup_context_mocks(tenant, user=None):
    """Return context manager patches for tenant context middleware."""
    if user is None:
        user = _make_user(tenant.id if tenant else "t-001")
    return (
        patch("middleware.tenant_context.user_service", **{
            "get_user_by_external_id": AsyncMock(return_value=user),
        }),
        patch("middleware.tenant_context.tenant_service", **{
            "get_tenant": AsyncMock(return_value=tenant),
        }),
        patch("middleware.tenant_context.settings", **{
            "skip_auth": True,
            "cosmos_db_endpoint": "https://fake.documents.azure.com/",
        }),
    )


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# POST /api/v1/projects — Create project
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_project_returns_201(client):
    """POST /api/v1/projects creates a project and returns 201."""
    tenant = _make_tenant()
    project = _make_project(name="New Project")

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.create_project = AsyncMock(return_value=project)

            response = await client.post(
                "/api/v1/projects",
                json={"name": "New Project"},
            )
            assert response.status_code == 201
            body = response.json()
            assert body["data"]["name"] == "New Project"
            assert body["data"]["status"] == "active"
            assert body["data"]["artifactCount"] == 0
            assert "meta" in body
            assert "request_id" in body["meta"]


@pytest.mark.asyncio
async def test_create_project_with_description(client):
    """POST /api/v1/projects with description returns 201."""
    tenant = _make_tenant()
    project = _make_project(name="My Project", description="A test project")

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.create_project = AsyncMock(return_value=project)

            response = await client.post(
                "/api/v1/projects",
                json={"name": "My Project", "description": "A test project"},
            )
            assert response.status_code == 201
            body = response.json()
            assert body["data"]["description"] == "A test project"


@pytest.mark.asyncio
async def test_create_project_requires_name(client):
    """POST /api/v1/projects without name returns 422."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        response = await client.post(
            "/api/v1/projects",
            json={},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_project_name_too_long(client):
    """POST /api/v1/projects with name > 100 chars returns 422."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        response = await client.post(
            "/api/v1/projects",
            json={"name": "x" * 101},
        )
        assert response.status_code == 422


@pytest.mark.asyncio
async def test_create_project_returns_401_without_tenant(client):
    """POST /api/v1/projects returns 401 when tenant context is missing."""
    response = await client.post(
        "/api/v1/projects",
        json={"name": "My Project"},
    )
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GET /api/v1/projects — List projects
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_list_projects_returns_paginated(client):
    """GET /api/v1/projects returns paginated project list."""
    tenant = _make_tenant()
    projects = [_make_project(f"prj-{i}", name=f"Project {i}") for i in range(3)]

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.list_projects = AsyncMock(return_value=(projects, 3))

            response = await client.get("/api/v1/projects")
            assert response.status_code == 200
            body = response.json()
            assert len(body["data"]) == 3
            assert body["pagination"]["total_count"] == 3
            assert body["pagination"]["page"] == 1
            assert body["pagination"]["page_size"] == 20
            assert "meta" in body


@pytest.mark.asyncio
async def test_list_projects_pagination_params(client):
    """GET /api/v1/projects respects page and pageSize parameters."""
    tenant = _make_tenant()
    projects = [_make_project("prj-1", name="Project 1")]

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.list_projects = AsyncMock(return_value=(projects, 5))

            response = await client.get("/api/v1/projects?page=2&pageSize=2")
            assert response.status_code == 200
            body = response.json()
            assert body["pagination"]["page"] == 2
            assert body["pagination"]["page_size"] == 2
            assert body["pagination"]["total_count"] == 5
            assert body["pagination"]["total_pages"] == 3
            assert body["pagination"]["has_next_page"] is True


@pytest.mark.asyncio
async def test_list_projects_empty(client):
    """GET /api/v1/projects returns empty list when no projects exist."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.list_projects = AsyncMock(return_value=([], 0))

            response = await client.get("/api/v1/projects")
            assert response.status_code == 200
            body = response.json()
            assert body["data"] == []
            assert body["pagination"]["total_count"] == 0


# ---------------------------------------------------------------------------
# GET /api/v1/projects/{projectId} — Get project
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_project_returns_project(client):
    """GET /api/v1/projects/{id} returns project details."""
    tenant = _make_tenant()
    project = _make_project()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.get_project = AsyncMock(return_value=project)

            response = await client.get("/api/v1/projects/prj-001")
            assert response.status_code == 200
            body = response.json()
            assert body["data"]["id"] == "prj-001"
            assert body["data"]["name"] == "Test Project"


@pytest.mark.asyncio
async def test_get_project_returns_404_when_not_found(client):
    """GET /api/v1/projects/{id} returns 404 for non-existent project."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.get_project = AsyncMock(return_value=None)

            response = await client.get("/api/v1/projects/prj-nonexistent")
            assert response.status_code == 404
            body = response.json()
            assert body["error"]["code"] == "RESOURCE_NOT_FOUND"


@pytest.mark.asyncio
async def test_get_project_tenant_isolation(client):
    """GET /api/v1/projects/{id} returns 404 for another tenant's project."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            # Service returns None because project belongs to different tenant
            mock_svc.get_project = AsyncMock(return_value=None)

            response = await client.get("/api/v1/projects/prj-other-tenant")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# PATCH /api/v1/projects/{projectId} — Update project
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_update_project_name(client):
    """PATCH /api/v1/projects/{id} updates the project name."""
    tenant = _make_tenant()
    updated_project = _make_project(name="Updated Name")

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.update_project = AsyncMock(return_value=updated_project)

            response = await client.patch(
                "/api/v1/projects/prj-001",
                json={"name": "Updated Name"},
            )
            assert response.status_code == 200
            body = response.json()
            assert body["data"]["name"] == "Updated Name"


@pytest.mark.asyncio
async def test_update_project_returns_404_when_not_found(client):
    """PATCH /api/v1/projects/{id} returns 404 for non-existent project."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.update_project = AsyncMock(return_value=None)

            response = await client.patch(
                "/api/v1/projects/prj-nonexistent",
                json={"name": "Updated"},
            )
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# DELETE /api/v1/projects/{projectId} — Soft-delete project
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_delete_project_returns_204(client):
    """DELETE /api/v1/projects/{id} soft-deletes and returns 204."""
    tenant = _make_tenant()
    deleted_project = _make_project(status=ProjectStatus.DELETED)

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.delete_project = AsyncMock(return_value=deleted_project)

            response = await client.delete("/api/v1/projects/prj-001")
            assert response.status_code == 204


@pytest.mark.asyncio
async def test_delete_project_returns_404_when_not_found(client):
    """DELETE /api/v1/projects/{id} returns 404 for non-existent project."""
    tenant = _make_tenant()

    mock1, mock2, mock3 = _setup_context_mocks(tenant)
    with mock1, mock2, mock3:
        with patch("domains.projects.router.project_service") as mock_svc:
            mock_svc.delete_project = AsyncMock(return_value=None)

            response = await client.delete("/api/v1/projects/prj-nonexistent")
            assert response.status_code == 404


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


# ---------------------------------------------------------------------------
# Service-level tests — usage counter integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_create_project_increments_usage_counter():
    """ProjectService.create_project increments the tenant's project_count."""
    from domains.projects.models import CreateProjectRequest

    tenant_id = "t-001"
    user_id = "u-001"
    project = _make_project(name="New Project")
    request = CreateProjectRequest(name="New Project")

    with (
        patch("domains.projects.service.project_repository") as mock_proj_repo,
        patch("domains.projects.service.tenant_repository") as mock_tenant_repo,
    ):
        mock_proj_repo.create = AsyncMock(return_value=project)
        mock_tenant_repo.increment_usage = AsyncMock(return_value=_make_tenant())

        from domains.projects.service import project_service

        await project_service.create_project(request, tenant_id, user_id)

        mock_tenant_repo.increment_usage.assert_called_once_with(tenant_id, "project_count")


@pytest.mark.asyncio
async def test_delete_project_decrements_usage_counter():
    """ProjectService.delete_project decrements the tenant's project_count."""
    tenant_id = "t-001"
    deleted_project = _make_project(status=ProjectStatus.DELETED)

    with (
        patch("domains.projects.service.project_repository") as mock_proj_repo,
        patch("domains.projects.service.tenant_repository") as mock_tenant_repo,
    ):
        mock_proj_repo.soft_delete = AsyncMock(return_value=deleted_project)
        mock_tenant_repo.increment_usage = AsyncMock(return_value=_make_tenant())

        from domains.projects.service import project_service

        await project_service.delete_project(tenant_id, "prj-001")

        mock_tenant_repo.increment_usage.assert_called_once_with(
            tenant_id, "project_count", amount=-1
        )


@pytest.mark.asyncio
async def test_delete_project_not_found_does_not_decrement():
    """ProjectService.delete_project does not decrement when project is not found."""
    tenant_id = "t-001"

    with (
        patch("domains.projects.service.project_repository") as mock_proj_repo,
        patch("domains.projects.service.tenant_repository") as mock_tenant_repo,
    ):
        mock_proj_repo.soft_delete = AsyncMock(return_value=None)
        mock_tenant_repo.increment_usage = AsyncMock()

        from domains.projects.service import project_service

        result = await project_service.delete_project(tenant_id, "prj-nonexistent")

        assert result is None
        mock_tenant_repo.increment_usage.assert_not_called()


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def test_project_routes_registered():
    """Project routes are registered in the app."""
    routes = [route.path for route in app.routes if hasattr(route, "path")]
    assert "/api/v1/projects" in routes
    assert "/api/v1/projects/{project_id}" in routes
