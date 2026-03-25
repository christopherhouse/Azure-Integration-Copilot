# Task 005 — Project and Artifact Domain

## Title

Implement project CRUD and artifact metadata endpoints with state machine.

## Objective

Build the project and artifact domain modules: project create/read/update/delete, artifact metadata management, artifact status state machine, and the Cosmos DB `projects` container. After this task, users can manage projects and the system has a place to track artifacts through their lifecycle.

## Why This Task Exists

The upload flow (task 006), parsing (task 008), and graph building (task 009) all depend on project and artifact entities existing with proper status tracking. The artifact state machine is the backbone of the async processing pipeline.

## In Scope

- Project CRUD endpoints
- Artifact metadata endpoints (list, get, delete — upload is task 006)
- Artifact status enum and state machine with valid transitions
- Cosmos DB `projects` container creation and document operations
- Project listing with pagination
- Artifact listing with pagination and status filtering
- Quota enforcement integration (project count checked via middleware)
- Soft-delete for projects and artifacts

## Out of Scope

- Artifact file upload to Blob Storage (task 006)
- Artifact type detection (task 006)
- Event publishing (task 006/007)
- Parsing, graph building, or analysis
- Frontend UI for projects (can be started in parallel)

## Dependencies

- **Task 002** (API foundation): Cosmos DB client, error handling, response envelopes.
- **Task 004** (tenancy/auth): Tenant context middleware, quota middleware, auth validation.

## Files/Directories Expected to Be Created or Modified

```
src/backend/
├── domains/
│   ├── projects/
│   │   ├── __init__.py
│   │   ├── router.py              # Project CRUD routes
│   │   ├── service.py             # ProjectService
│   │   ├── models.py              # Project, CreateProject, UpdateProject
│   │   └── repository.py          # Cosmos DB operations for projects
│   └── artifacts/
│       ├── __init__.py
│       ├── router.py              # Artifact metadata routes (no upload yet)
│       ├── service.py             # ArtifactService
│       ├── models.py              # Artifact, ArtifactStatus, ArtifactError
│       └── repository.py          # Cosmos DB operations for artifacts
├── main.py                        # Updated: register project and artifact routers
tests/backend/
├── test_projects.py
├── test_artifacts.py
└── test_artifact_state_machine.py
```

## Implementation Notes

### Project Endpoints

| Method | Path | Handler |
|--------|------|---------|
| `POST` | `/api/v1/projects` | Create project (check `maxProjects` quota) |
| `GET` | `/api/v1/projects` | List projects for tenant (paginated) |
| `GET` | `/api/v1/projects/{projectId}` | Get project by ID |
| `PATCH` | `/api/v1/projects/{projectId}` | Update project name/description |
| `DELETE` | `/api/v1/projects/{projectId}` | Soft-delete project |

### Project Models

```python
class CreateProjectRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=100)
    description: str | None = Field(None, max_length=500)

class ProjectResponse(BaseModel):
    id: str
    name: str
    description: str | None
    status: str
    artifact_count: int
    graph_version: int
    created_by: str
    created_at: datetime
    updated_at: datetime
```

### Artifact Status State Machine

```python
class ArtifactStatus(str, Enum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    SCANNING = "scanning"
    SCAN_PASSED = "scan_passed"
    SCAN_FAILED = "scan_failed"
    PARSING = "parsing"
    PARSED = "parsed"
    PARSE_FAILED = "parse_failed"
    GRAPH_BUILDING = "graph_building"
    GRAPH_BUILT = "graph_built"
    GRAPH_FAILED = "graph_failed"
    UNSUPPORTED = "unsupported"

VALID_TRANSITIONS: dict[ArtifactStatus, set[ArtifactStatus]] = {
    ArtifactStatus.UPLOADING: {ArtifactStatus.UPLOADED, ArtifactStatus.UNSUPPORTED},
    ArtifactStatus.UPLOADED: {ArtifactStatus.SCANNING},
    ArtifactStatus.SCANNING: {ArtifactStatus.SCAN_PASSED, ArtifactStatus.SCAN_FAILED},
    ArtifactStatus.SCAN_PASSED: {ArtifactStatus.PARSING},
    ArtifactStatus.PARSING: {ArtifactStatus.PARSED, ArtifactStatus.PARSE_FAILED},
    ArtifactStatus.PARSED: {ArtifactStatus.GRAPH_BUILDING},
    ArtifactStatus.GRAPH_BUILDING: {ArtifactStatus.GRAPH_BUILT, ArtifactStatus.GRAPH_FAILED},
}

def transition_status(current: ArtifactStatus, target: ArtifactStatus) -> ArtifactStatus:
    valid = VALID_TRANSITIONS.get(current, set())
    if target not in valid:
        raise InvalidStatusTransition(current=current, target=target)
    return target
```

### Cosmos DB Container: `projects`

| Property | Value |
|----------|-------|
| Container name | `projects` |
| Partition key | `/partitionKey` |
| Partition key value | `{tenantId}` |
| Document types | `project`, `artifact` |

### Repository Pattern

```python
class ProjectRepository:
    def __init__(self, cosmos: CosmosService):
        self.container = cosmos.get_container("integration-copilot", "projects")

    async def create(self, project: dict) -> dict:
        return await self.container.create_item(project)

    async def get_by_id(self, tenant_id: str, project_id: str) -> dict | None:
        try:
            return await self.container.read_item(project_id, partition_key=tenant_id)
        except CosmosResourceNotFoundError:
            return None

    async def list_by_tenant(self, tenant_id: str, page: int, page_size: int) -> tuple[list[dict], int]:
        query = "SELECT * FROM c WHERE c.partitionKey = @tenantId AND c.type = 'project' AND c.status != 'deleted' ORDER BY c.createdAt DESC"
        # Execute with pagination
```

### Soft Delete

Soft delete sets `status = "deleted"` and `deletedAt = now()`. List queries filter out deleted items. Hard delete is a future background job.

### Tenant Scoping

Every query includes the `partitionKey` (tenant ID). The service layer reads `tenant_id` from `request.state.tenant.id` and passes it to the repository. No query runs without tenant scoping.

## Acceptance Criteria

- [ ] `POST /api/v1/projects` creates a project and returns 201
- [ ] `POST /api/v1/projects` returns 429 when `maxProjects` limit is reached
- [ ] `GET /api/v1/projects` returns paginated project list for the tenant
- [ ] `GET /api/v1/projects/{id}` returns project details
- [ ] `GET /api/v1/projects/{id}` returns 404 for another tenant's project
- [ ] `PATCH /api/v1/projects/{id}` updates project name/description
- [ ] `DELETE /api/v1/projects/{id}` soft-deletes the project
- [ ] Artifact status enum is defined with all statuses
- [ ] `transition_status()` enforces valid transitions and raises on invalid ones
- [ ] `GET /api/v1/projects/{id}/artifacts` returns paginated artifact list (empty for now)
- [ ] All queries are tenant-scoped
- [ ] Tests pass for project CRUD, artifact state machine

## Definition of Done

- Project CRUD works end-to-end with Cosmos DB.
- Artifact metadata model and state machine are implemented and tested.
- Quota enforcement works for project creation.
- The upload task (006) can create artifact metadata and transition statuses.

## Risks / Gotchas

- **Cosmos DB container creation**: The `projects` container must be created before first use. Consider a startup check or manual creation.
- **Pagination with Cosmos DB**: Use continuation tokens internally but expose page/pageSize to the API. May need to use OFFSET/LIMIT for simplicity in MVP.
- **Concurrent project creation**: Two rapid requests could exceed the quota. ETag-based counter updates mitigate this.

## Suggested Validation Steps

1. Create a project: `POST /api/v1/projects` with `{ "name": "Test Project" }`.
2. List projects: `GET /api/v1/projects` → verify the project appears.
3. Get project: `GET /api/v1/projects/{id}` → verify details.
4. Update project: `PATCH /api/v1/projects/{id}` with `{ "name": "Updated" }`.
5. Delete project: `DELETE /api/v1/projects/{id}` → verify soft-delete.
6. List projects again → deleted project should not appear.
7. Test state machine: write unit tests for all valid and invalid transitions.
8. Run all tests: `uv run pytest tests/backend/ -v`.
