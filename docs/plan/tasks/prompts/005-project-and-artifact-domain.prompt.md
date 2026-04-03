# Prompt — Execute Task 005: Project and Artifact Domain

You are an expert Python backend engineer. Execute the following task to implement the project and artifact domain for Integrisight.ai.

## Context

Read these documents before starting:

- **Task spec**: `docs/plan/tasks/005-project-and-artifact-domain.md`
- **Projects and artifacts domain**: `docs/plan/03-domain-projects-and-artifacts.md`
- **API design**: `docs/plan/07-api-design.md`

**Prerequisites**: Tasks 002 (API foundation) and 004 (tenancy/auth) must be complete. Cosmos DB client, tenant context middleware, and quota enforcement must be working.

## What You Must Do

Build the project and artifact domain modules with CRUD endpoints, the artifact status state machine, and the Cosmos DB `projects` container.

### Step 1 — Project Models

Create `src/backend/domains/projects/models.py`:
- `CreateProjectRequest` — name (str, 1–100 chars), description (str | None, max 500)
- `UpdateProjectRequest` — name (str | None), description (str | None)
- `ProjectResponse` — id, name, description, status, artifact_count, graph_version, created_by, created_at, updated_at
- Project statuses: `active`, `archived`, `deleted`

### Step 2 — Artifact Models and State Machine

Create `src/backend/domains/artifacts/models.py`:
- `ArtifactStatus` enum with all 12 statuses: `uploading`, `uploaded`, `scanning`, `scan_passed`, `scan_failed`, `parsing`, `parsed`, `parse_failed`, `graph_building`, `graph_built`, `graph_failed`, `unsupported`
- `VALID_TRANSITIONS` dict mapping each status to its valid next statuses (see task spec)
- `transition_status(current, target)` function that raises `InvalidStatusTransition` if the transition is not valid
- `ArtifactResponse` — id, name, artifact_type, status, file_size_bytes, content_hash, error, created_at, updated_at
- `ArtifactError` — code, message, occurred_at

### Step 3 — Project Repository

Create `src/backend/domains/projects/repository.py`:
- Cosmos DB operations for the `projects` container (partition key: `{tenantId}`)
- `create()`, `get_by_id()`, `list_by_tenant()` (paginated, exclude deleted), `update()`, `soft_delete()`
- All queries include tenant ID scoping.

### Step 4 — Artifact Repository

Create `src/backend/domains/artifacts/repository.py`:
- Cosmos DB operations for artifacts in the `projects` container
- `create()`, `get_by_id()`, `list_by_project()` (paginated, filterable by status), `update_status()`, `soft_delete()`
- All queries scoped by tenant ID.

### Step 5 — Project Service and Routes

Create `src/backend/domains/projects/service.py` — `ProjectService` with create, get, list, update, delete methods.

Create `src/backend/domains/projects/router.py`:
- `POST /api/v1/projects` — create project (quota middleware checks `max_projects`). Returns 201.
- `GET /api/v1/projects` — list projects (paginated). Query params: `page`, `page_size`.
- `GET /api/v1/projects/{projectId}` — get project. Returns 404 for missing or other-tenant projects.
- `PATCH /api/v1/projects/{projectId}` — update name/description.
- `DELETE /api/v1/projects/{projectId}` — soft-delete.

### Step 6 — Artifact Metadata Routes

Create `src/backend/domains/artifacts/service.py` — `ArtifactService` with list and get methods (upload is task 006).

Create `src/backend/domains/artifacts/router.py`:
- `GET /api/v1/projects/{projectId}/artifacts` — list artifacts (paginated, filterable by status).
- `GET /api/v1/projects/{projectId}/artifacts/{artifactId}` — get artifact metadata.
- `DELETE /api/v1/projects/{projectId}/artifacts/{artifactId}` — soft-delete artifact.

### Step 7 — Register Routers

Update `src/backend/main.py` to register the project and artifact routers.

### Step 8 — Tests

Create tests:
- `tests/backend/test_projects.py` — test project CRUD, pagination, tenant isolation.
- `tests/backend/test_artifacts.py` — test artifact listing and metadata retrieval.
- `tests/backend/test_artifact_state_machine.py` — test all valid and invalid status transitions.

### Step 9 — Validation

1. Create a project: `POST /api/v1/projects` with `{ "name": "Test Project" }` → 201.
2. List projects: `GET /api/v1/projects` → project appears.
3. Get project: `GET /api/v1/projects/{id}` → project details.
4. Update project: `PATCH /api/v1/projects/{id}` with `{ "name": "Updated" }`.
5. Delete project: `DELETE /api/v1/projects/{id}` → soft-deleted.
6. List again → deleted project absent.
7. Artifact list returns empty: `GET /api/v1/projects/{id}/artifacts` → `[]`.
8. Verify `transition_status` rejects invalid transitions (unit tests).
9. `uv run pytest tests/backend/ -v` — all tests pass.

## Constraints

- All queries must be tenant-scoped — no cross-tenant data access.
- Soft-delete sets `status = "deleted"` and a `deletedAt` timestamp. List queries exclude deleted items.
- Do not implement file upload (task 006), event publishing (task 007), or parsing (task 008).
- Project quota uses the existing middleware from task 004.
- Cosmos DB container creation should be handled at startup or manually.

## Done When

- Project CRUD works end-to-end with Cosmos DB.
- Artifact status state machine is implemented and tested.
- Pagination works for project and artifact listing.
- Tenant isolation is enforced on all queries.
- Task 006 can create artifact metadata and transition statuses.
