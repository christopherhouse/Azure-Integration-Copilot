# Prompt — Execute Task 002: API Foundation

You are an expert Python backend engineer. Execute the following task to build the FastAPI application foundation for Integration Copilot.

## Context

Read these documents before starting:

- **Task spec**: `docs/plan/tasks/002-api-foundation.md`
- **System architecture**: `docs/plan/01-system-architecture.md`
- **API design**: `docs/plan/07-api-design.md`

**Prerequisite**: Task 001 (monorepo scaffold) must be complete. The Python project at `src/backend/` must exist with FastAPI installed.

## What You Must Do

Build the FastAPI application skeleton with middleware stubs, shared utilities, Azure SDK client wrappers, error handling, response envelopes, and health endpoints.

### Step 1 — Configuration

Create `src/backend/config.py` with a `Settings` class using `pydantic_settings.BaseSettings`:
- Fields: `environment`, `cosmos_db_endpoint`, `blob_storage_endpoint`, `event_grid_namespace_endpoint`, `event_grid_topic` (default: `"integration-events"`), `web_pubsub_endpoint`, `azure_client_id`, `applicationinsights_connection_string`, `defender_scan_enabled` (default: `False`).
- Load from `.env` file.
- Add `pydantic-settings` to `pyproject.toml` dependencies if not present.

### Step 2 — Shared Models

Create `src/backend/shared/models.py` with Pydantic v2 models:
- `Meta` (request_id: str, timestamp: datetime)
- `ResponseEnvelope[T]` (data: T, meta: Meta) — generic
- `PaginationInfo` (page, page_size, total_count, total_pages, has_next_page)
- `PaginatedResponse[T]` (data: list[T], meta: Meta, pagination: PaginationInfo) — generic
- `ErrorDetail` (code: str, message: str, detail: dict | None, request_id: str | None)
- `ErrorResponse` (error: ErrorDetail)

### Step 3 — Exception Classes

Create `src/backend/shared/exceptions.py`:
- `AppError(Exception)` — base with `status_code`, `code`, `message`, `detail`
- `NotFoundError(AppError)` — 404, code `"RESOURCE_NOT_FOUND"`
- `QuotaExceededError(AppError)` — 429, code `"QUOTA_EXCEEDED"`
- `ValidationError(AppError)` — 422, code `"VALIDATION_ERROR"`
- `ForbiddenError(AppError)` — 403, code `"FORBIDDEN"`
- `UnauthorizedError(AppError)` — 401, code `"UNAUTHORIZED"`

### Step 4 — Azure SDK Client Wrappers

Create these wrappers, each using `DefaultAzureCredential` from `azure.identity.aio`:
- `src/backend/shared/cosmos.py` — `CosmosService` class wrapping `azure.cosmos.aio.CosmosClient`
- `src/backend/shared/blob.py` — `BlobService` class wrapping `azure.storage.blob.aio.BlobServiceClient`
- `src/backend/shared/events.py` — `EventGridPublisher` class wrapping Event Grid Namespace publish API

### Step 5 — Structured Logging

Create `src/backend/shared/logging.py`:
- Configure `structlog` to output JSON in production, colored console in development.
- Add a request-scoped `request_id` to all log entries.

### Step 6 — Middleware Stubs

Create middleware stubs with correct signatures but minimal logic:
- `src/backend/middleware/auth.py` — Look for `Authorization: Bearer` header, set `request.state.user_id` to a hardcoded dev value. Skip auth for `/api/v1/health*` paths.
- `src/backend/middleware/tenant_context.py` — Set `request.state.tenant` and `request.state.tier` to hardcoded dev values.
- `src/backend/middleware/quota.py` — Pass through all requests (no enforcement yet).

### Step 7 — Update main.py

Update `src/backend/main.py`:
- Register middleware (auth → tenant_context → quota order).
- Register custom exception handlers that convert `AppError` subclasses into `ErrorResponse` format.
- Add `GET /api/v1/health` returning `ResponseEnvelope` with `{"status": "ok"}`.
- Add `GET /api/v1/health/ready` that attempts Cosmos DB connectivity (fail gracefully with 503 if not configured).
- Add a 404 handler for unknown routes.

### Step 8 — Tests

Create tests under `tests/backend/`:
- `conftest.py` — shared fixtures with `TestClient`, mock config.
- `test_health.py` — test health and ready endpoints.
- `test_error_handling.py` — test that `NotFoundError`, `QuotaExceededError` produce correct HTTP status and error format.

### Step 9 — Validation

1. `uv run uvicorn main:app --reload --port 8000` — starts without errors.
2. `curl http://localhost:8000/api/v1/health` — returns 200 with `{ "data": { "status": "ok" }, "meta": { ... } }`.
3. `curl http://localhost:8000/api/v1/health/ready` — returns 200 or 503 gracefully.
4. `curl http://localhost:8000/api/v1/nonexistent` — returns 404 with `{ "error": { "code": "RESOURCE_NOT_FOUND", ... } }`.
5. `uv run pytest tests/backend/ -v` — all tests pass.
6. `uv run ruff check src/backend/` — passes.

## Constraints

- All models must use Pydantic v2 syntax.
- Use async Azure SDK clients (`from azure.cosmos.aio`, etc.).
- Middleware stubs must set `request.state` values so downstream code can depend on them immediately.
- Do not implement real JWT validation, real tenant resolution, or real quota enforcement — those are task 004.
- Do not create domain routes (projects, artifacts, etc.) — those are tasks 005+.

## Done When

- Health endpoints return properly enveloped responses.
- Error responses follow the standard format from doc 07-api-design.md.
- Azure SDK clients are wrapped and ready for use.
- Middleware stubs populate `request.state.user_id`, `request.state.tenant`, and `request.state.tier`.
- All tests pass.
- A domain module can add a new router and immediately use tenant context, error handling, and Cosmos DB access.
