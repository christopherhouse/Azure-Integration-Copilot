"""Tests for project CRUD endpoints."""

import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import AsyncMock, call, patch

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
from domains.tenants.models import FREE_TIER, Tenant, TenantStatus, Usage, User, UserRole, UserStatus
from shared.exceptions import QuotaExceededError


def _make_tenant(tenant_id: str = "t-001", display_name: str = "Test Tenant", project_count: int = 0) -> Tenant:
    now = datetime.now(UTC)
    return Tenant(
        id=tenant_id,
        partitionKey=tenant_id,
        displayName=display_name,
        ownerId="u-001",
        tierId="tier_free",
        status=TenantStatus.ACTIVE,
        usage=Usage(project_count=project_count, daily_analysis_reset_at=now),
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
        patch("domains.projects.service.tier_service") as mock_tier_svc,
    ):
        mock_tenant_repo.increment_usage = AsyncMock(
            return_value=_make_tenant(project_count=1)
        )
        mock_tier_svc.get_tier.return_value = FREE_TIER
        mock_proj_repo.create = AsyncMock(return_value=project)

        from domains.projects.service import project_service

        result = await project_service.create_project(request, tenant_id, user_id)

        mock_tenant_repo.increment_usage.assert_called_once_with(tenant_id, "project_count")
        mock_proj_repo.create.assert_called_once()
        assert result == project


@pytest.mark.asyncio
async def test_create_project_raises_quota_exceeded_when_at_limit():
    """ProjectService.create_project raises QuotaExceededError when project_count exceeds max."""
    from domains.projects.models import CreateProjectRequest

    tenant_id = "t-001"
    user_id = "u-001"
    request = CreateProjectRequest(name="Over Limit")

    with (
        patch("domains.projects.service.project_repository"),
        patch("domains.projects.service.tenant_repository") as mock_tenant_repo,
        patch("domains.projects.service.tier_service") as mock_tier_svc,
    ):
        # increment returns a tenant with count exceeding the limit (4 > 3)
        mock_tenant_repo.increment_usage = AsyncMock(
            side_effect=[
                _make_tenant(project_count=4),  # after increment — over limit
                _make_tenant(project_count=3),  # after rollback
            ]
        )
        mock_tier_svc.get_tier.return_value = FREE_TIER

        from domains.projects.service import project_service

        with pytest.raises(QuotaExceededError) as exc_info:
            await project_service.create_project(request, tenant_id, user_id)

        assert exc_info.value.status_code == 429
        mock_tier_svc.get_tier.assert_called_once_with(FREE_TIER.id)
        # Verify rollback was called
        calls = mock_tenant_repo.increment_usage.call_args_list
        assert len(calls) == 2
        assert calls[0] == call(tenant_id, "project_count")
        assert calls[1] == call(tenant_id, "project_count", amount=-1)


@pytest.mark.asyncio
async def test_create_project_rolls_back_counter_on_creation_failure():
    """ProjectService.create_project rolls back counter when project creation fails."""
    from domains.projects.models import CreateProjectRequest

    tenant_id = "t-001"
    user_id = "u-001"
    request = CreateProjectRequest(name="Fails to Create")

    with (
        patch("domains.projects.service.project_repository") as mock_proj_repo,
        patch("domains.projects.service.tenant_repository") as mock_tenant_repo,
        patch("domains.projects.service.tier_service") as mock_tier_svc,
    ):
        mock_tenant_repo.increment_usage = AsyncMock(
            side_effect=[
                _make_tenant(project_count=1),  # after increment — under limit
                _make_tenant(project_count=0),  # after rollback
            ]
        )
        mock_tier_svc.get_tier.return_value = FREE_TIER
        mock_proj_repo.create = AsyncMock(side_effect=RuntimeError("DB write failed"))

        from domains.projects.service import project_service

        with pytest.raises(RuntimeError, match="DB write failed"):
            await project_service.create_project(request, tenant_id, user_id)

        # Verify rollback was called
        calls = mock_tenant_repo.increment_usage.call_args_list
        assert len(calls) == 2
        assert calls[0] == call(tenant_id, "project_count")
        assert calls[1] == call(tenant_id, "project_count", amount=-1)


@pytest.mark.asyncio
async def test_create_project_raises_quota_exceeded_when_tenant_not_found():
    """ProjectService.create_project raises QuotaExceededError when tenant is not found."""
    from domains.projects.models import CreateProjectRequest

    tenant_id = "t-nonexistent"
    user_id = "u-001"
    request = CreateProjectRequest(name="No Tenant")

    with (
        patch("domains.projects.service.project_repository"),
        patch("domains.projects.service.tenant_repository") as mock_tenant_repo,
        patch("domains.projects.service.tier_service"),
    ):
        mock_tenant_repo.increment_usage = AsyncMock(return_value=None)

        from domains.projects.service import project_service

        with pytest.raises(QuotaExceededError) as exc_info:
            await project_service.create_project(request, tenant_id, user_id)

        assert exc_info.value.status_code == 429


@pytest.mark.asyncio
async def test_delete_project_decrements_usage_counter():
    """ProjectService.delete_project decrements the tenant's project_count."""
    tenant_id = "t-001"
    project = _make_project()
    deleted_project = _make_project(status=ProjectStatus.DELETED)

    with (
        patch("domains.projects.service.project_repository") as mock_proj_repo,
        patch("domains.projects.service.artifact_repository") as mock_art_repo,
        patch("domains.projects.service.graph_repository") as mock_graph_repo,
        patch("domains.projects.service.tenant_repository") as mock_tenant_repo,
    ):
        mock_proj_repo.get_by_id = AsyncMock(return_value=project)
        mock_proj_repo.soft_delete = AsyncMock(return_value=deleted_project)
        mock_art_repo.soft_delete_all_by_project = AsyncMock(return_value=0)
        mock_graph_repo.delete_all_by_project = AsyncMock(return_value=0)
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
        patch("domains.projects.service.artifact_repository") as mock_art_repo,
        patch("domains.projects.service.graph_repository") as mock_graph_repo,
        patch("domains.projects.service.tenant_repository") as mock_tenant_repo,
    ):
        mock_proj_repo.get_by_id = AsyncMock(return_value=None)
        mock_art_repo.soft_delete_all_by_project = AsyncMock(return_value=0)
        mock_graph_repo.delete_all_by_project = AsyncMock(return_value=0)
        mock_tenant_repo.increment_usage = AsyncMock()

        from domains.projects.service import project_service

        result = await project_service.delete_project(tenant_id, "prj-nonexistent")

        assert result is None
        mock_tenant_repo.increment_usage.assert_not_called()


@pytest.mark.asyncio
async def test_delete_project_cascades_to_artifacts_and_graph():
    """ProjectService.delete_project soft-deletes artifacts and deletes graph data."""
    tenant_id = "t-001"
    project_id = "prj-001"
    project = _make_project(project_id=project_id, tenant_id=tenant_id)
    deleted_project = _make_project(
        project_id=project_id, tenant_id=tenant_id, status=ProjectStatus.DELETED
    )

    with (
        patch("domains.projects.service.project_repository") as mock_proj_repo,
        patch("domains.projects.service.artifact_repository") as mock_art_repo,
        patch("domains.projects.service.graph_repository") as mock_graph_repo,
        patch("domains.projects.service.tenant_repository") as mock_tenant_repo,
    ):
        mock_proj_repo.get_by_id = AsyncMock(return_value=project)
        mock_proj_repo.soft_delete = AsyncMock(return_value=deleted_project)
        mock_art_repo.soft_delete_all_by_project = AsyncMock(return_value=3)
        mock_graph_repo.delete_all_by_project = AsyncMock(return_value=5)
        mock_tenant_repo.increment_usage = AsyncMock(return_value=_make_tenant())

        from domains.projects.service import project_service

        result = await project_service.delete_project(tenant_id, project_id)

        assert result is not None
        mock_art_repo.soft_delete_all_by_project.assert_called_once_with(
            tenant_id, project_id
        )
        mock_graph_repo.delete_all_by_project.assert_called_once_with(
            f"{tenant_id}:{project_id}"
        )
        # Artifact count decremented by 3 (the number of deleted artifacts)
        mock_tenant_repo.increment_usage.assert_any_call(
            tenant_id, "total_artifact_count", amount=-3
        )
        # Project count decremented by 1
        mock_tenant_repo.increment_usage.assert_any_call(
            tenant_id, "project_count", amount=-1
        )


@pytest.mark.asyncio
async def test_delete_project_no_artifacts_skips_artifact_count_decrement():
    """ProjectService.delete_project skips artifact count update when no artifacts exist."""
    tenant_id = "t-001"
    project_id = "prj-001"
    project = _make_project()
    deleted_project = _make_project(status=ProjectStatus.DELETED)

    with (
        patch("domains.projects.service.project_repository") as mock_proj_repo,
        patch("domains.projects.service.artifact_repository") as mock_art_repo,
        patch("domains.projects.service.graph_repository") as mock_graph_repo,
        patch("domains.projects.service.tenant_repository") as mock_tenant_repo,
    ):
        mock_proj_repo.get_by_id = AsyncMock(return_value=project)
        mock_proj_repo.soft_delete = AsyncMock(return_value=deleted_project)
        mock_art_repo.soft_delete_all_by_project = AsyncMock(return_value=0)
        mock_graph_repo.delete_all_by_project = AsyncMock(return_value=0)
        mock_tenant_repo.increment_usage = AsyncMock(return_value=_make_tenant())

        from domains.projects.service import project_service

        await project_service.delete_project(tenant_id, project_id)

        # Only project_count should be decremented — no artifact count call
        mock_tenant_repo.increment_usage.assert_called_once_with(
            tenant_id, "project_count", amount=-1
        )


# ---------------------------------------------------------------------------
# Route registration
# ---------------------------------------------------------------------------


def test_project_routes_registered():
    """Project routes are registered in the app."""
    routes = [route.path for route in app.routes if hasattr(route, "path")]
    assert "/api/v1/projects" in routes
    assert "/api/v1/projects/{project_id}" in routes


# ---------------------------------------------------------------------------
# ProjectRepository.increment_artifact_count unit tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_project_repository_increment_artifact_count():
    """ProjectRepository.increment_artifact_count reads, increments, and writes back."""
    from domains.projects.repository import ProjectRepository

    project = Project(
        id="prj-001",
        partitionKey="t-001",
        tenantId="t-001",
        name="Test",
        createdBy="u-001",
        artifactCount=5,
    )
    project.etag = "etag-1"

    updated_project = project.model_copy()
    updated_project.artifact_count = 6
    updated_project.etag = "etag-2"

    repo = ProjectRepository()

    with (
        patch.object(repo, "get_by_id", new_callable=AsyncMock, return_value=project),
        patch.object(repo, "update", new_callable=AsyncMock, return_value=updated_project),
    ):
        result = await repo.increment_artifact_count("t-001", "prj-001")

        assert result is not None
        repo.get_by_id.assert_called_once_with("t-001", "prj-001")
        repo.update.assert_called_once()
        # The project passed to update should have artifact_count=6
        updated_arg = repo.update.call_args[0][0]
        assert updated_arg.artifact_count == 6


@pytest.mark.asyncio
async def test_project_repository_increment_artifact_count_floors_at_zero():
    """Decrementing artifact_count below zero floors at 0."""
    from domains.projects.repository import ProjectRepository

    project = Project(
        id="prj-001",
        partitionKey="t-001",
        tenantId="t-001",
        name="Test",
        createdBy="u-001",
        artifactCount=0,
    )
    project.etag = "etag-1"

    updated_project = project.model_copy()
    updated_project.artifact_count = 0
    updated_project.etag = "etag-2"

    repo = ProjectRepository()

    with (
        patch.object(repo, "get_by_id", new_callable=AsyncMock, return_value=project),
        patch.object(repo, "update", new_callable=AsyncMock, return_value=updated_project),
    ):
        result = await repo.increment_artifact_count("t-001", "prj-001", amount=-1)

        assert result is not None
        # The project passed to update should have artifact_count=0, not -1
        updated_arg = repo.update.call_args[0][0]
        assert updated_arg.artifact_count == 0
