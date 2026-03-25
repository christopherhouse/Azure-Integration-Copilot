# Task 002 — API Foundation

## Title

Build the FastAPI application skeleton with middleware, shared utilities, and health endpoints.

## Objective

Establish the API application structure with error handling, request/response envelopes, shared Azure SDK client wrappers, and the middleware pipeline. This creates the foundation that all domain modules build on.

## Why This Task Exists

Domain modules (tenants, projects, artifacts, graph, analysis) all depend on shared infrastructure: error handling, response envelopes, Cosmos DB and Blob clients, and the middleware chain. Building this first prevents each domain task from re-inventing these patterns.

## In Scope

- FastAPI application entry point with router registration pattern
- Health endpoints (`/api/v1/health`, `/api/v1/health/ready`)
- Application configuration module (environment variables, settings)
- Standard error handling (exception handlers, error response format)
- Standard response envelope (`{ data, meta }`)
- Shared Pydantic models (IDs, pagination, timestamps)
- Cosmos DB async client wrapper
- Blob Storage async client wrapper
- Event Grid publisher wrapper (publish-only; consumers are in task 007)
- Application exception classes
- Structured logging setup with structlog
- Middleware pipeline skeleton (auth, tenant context, quota — stubs for now)

## Out of Scope

- Actual JWT validation (task 004)
- Tenant resolution (task 004)
- Quota enforcement logic (task 004)
- Domain routes (tasks 005+)
- Worker code
- Frontend changes
- Database container creation (Cosmos DB containers are created per-domain)

## Dependencies

- **Task 001** (monorepo scaffold): Python project must exist with `pyproject.toml` and FastAPI installed.

## Files/Directories Expected to Be Created or Modified

```
src/backend/
├── main.py                        # Updated: router registration, middleware, exception handlers
├── config.py                      # Settings class with environment variable loading
├── middleware/
│   ├── __init__.py
│   ├── auth.py                    # Stub: extracts token, sets request.state.user_id
│   ├── tenant_context.py          # Stub: sets request.state.tenant (hardcoded for now)
│   └── quota.py                   # Stub: passes through (no enforcement yet)
├── shared/
│   ├── __init__.py
│   ├── models.py                  # ResponseEnvelope, PaginatedResponse, ErrorResponse, ID types
│   ├── cosmos.py                  # CosmosClient wrapper (async, managed identity)
│   ├── blob.py                    # BlobServiceClient wrapper (async, managed identity)
│   ├── events.py                  # EventGridPublisher wrapper
│   ├── exceptions.py              # AppError, NotFoundError, QuotaExceededError, etc.
│   └── logging.py                 # Structlog configuration
├── domains/
│   └── __init__.py                # Empty, ready for domain modules
tests/backend/
├── conftest.py                    # Shared test fixtures (TestClient, mock config)
├── test_health.py                 # Health endpoint tests
└── test_error_handling.py         # Error response format tests
```

## Implementation Notes

### Configuration

```python
# config.py
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    environment: str = "development"
    cosmos_db_endpoint: str = ""
    blob_storage_endpoint: str = ""
    event_grid_namespace_endpoint: str = ""
    event_grid_topic: str = "integration-events"
    web_pubsub_endpoint: str = ""
    azure_client_id: str = ""
    applicationinsights_connection_string: str = ""
    defender_scan_enabled: bool = False
    
    class Config:
        env_file = ".env"

settings = Settings()
```

### Response Envelope

```python
# shared/models.py
from pydantic import BaseModel
from datetime import datetime
from typing import Generic, TypeVar

T = TypeVar("T")

class Meta(BaseModel):
    request_id: str
    timestamp: datetime

class ResponseEnvelope(BaseModel, Generic[T]):
    data: T
    meta: Meta

class PaginationInfo(BaseModel):
    page: int
    page_size: int
    total_count: int
    total_pages: int
    has_next_page: bool

class PaginatedResponse(BaseModel, Generic[T]):
    data: list[T]
    meta: Meta
    pagination: PaginationInfo

class ErrorDetail(BaseModel):
    code: str
    message: str
    detail: dict | None = None
    request_id: str | None = None

class ErrorResponse(BaseModel):
    error: ErrorDetail
```

### Exception Handlers

Register custom exception handlers in `main.py` that convert `AppError` subclasses into the standard `ErrorResponse` format with appropriate HTTP status codes.

### Cosmos DB Client

```python
# shared/cosmos.py
from azure.cosmos.aio import CosmosClient
from azure.identity.aio import DefaultAzureCredential

class CosmosService:
    def __init__(self, endpoint: str):
        self.credential = DefaultAzureCredential()
        self.client = CosmosClient(endpoint, credential=self.credential)
    
    async def get_container(self, database: str, container: str):
        db = self.client.get_database_client(database)
        return db.get_container_client(container)
```

### Middleware Stubs

Create middleware classes with the correct signature but minimal logic. Auth middleware should look for a `Bearer` token but not validate it yet. Tenant context should set a hardcoded tenant for development. Quota middleware should pass through.

This allows domain tasks to write code that expects `request.state.tenant` and `request.state.user_id` from the start, even before real auth is implemented.

### Structured Logging

Configure `structlog` to output JSON in production and colored console output in development. Add a request-scoped `request_id` to all log entries.

## Acceptance Criteria

- [ ] `GET /api/v1/health` returns `{ "data": { "status": "ok" }, "meta": { ... } }`
- [ ] `GET /api/v1/health/ready` attempts Cosmos DB connectivity (can fail gracefully if not configured)
- [ ] A request to a nonexistent route returns `{ "error": { "code": "RESOURCE_NOT_FOUND", ... } }`
- [ ] Raising `NotFoundError` in a handler returns 404 with the standard error format
- [ ] Raising `QuotaExceededError` returns 429 with the standard error format
- [ ] All responses include `meta.request_id` and `meta.timestamp`
- [ ] `request.state.user_id` is set by the auth middleware stub
- [ ] `request.state.tenant` is set by the tenant context middleware stub
- [ ] Cosmos DB, Blob, and Event Grid client wrappers initialize without errors
- [ ] Structured logs are JSON-formatted
- [ ] Tests pass: `uv run pytest tests/backend/ -v`

## Definition of Done

- All shared utilities, middleware stubs, and health endpoints are implemented.
- Error handling follows the standard format from doc 07-api-design.md.
- Azure SDK clients are wrapped and ready for use by domain modules.
- Tests exist for health endpoints and error handling.
- A domain module task can add a new router and immediately use tenant context, error handling, and Cosmos DB access.

## Risks / Gotchas

- **Azure SDK in dev**: `DefaultAzureCredential` will fall back to Azure CLI or environment credentials in local dev. Ensure `.env` or Azure CLI is configured.
- **Cosmos DB not available locally**: Health ready endpoint should handle missing Cosmos gracefully (return 503, not crash).
- **Pydantic v2**: Ensure all models use Pydantic v2 syntax (`model_config` instead of `class Config`).
- **Async clients**: Use `azure-cosmos` async API (`from azure.cosmos.aio`).

## Suggested Validation Steps

1. Start the API: `uv run uvicorn main:app --reload --port 8000`
2. `curl http://localhost:8000/api/v1/health` — should return 200 with envelope
3. `curl http://localhost:8000/api/v1/health/ready` — should return 200 or 503 gracefully
4. `curl http://localhost:8000/api/v1/nonexistent` — should return 404 with error format
5. Run tests: `uv run pytest tests/backend/ -v`
6. Run linter: `uv run ruff check src/backend/`
7. Check logs: verify JSON output with `request_id`
