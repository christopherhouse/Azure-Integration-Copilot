# Developer Guide

This guide covers how to set up, develop, test, and run Integration Copilot locally.

## Prerequisites

| Tool | Version | Install |
|------|---------|---------|
| **Python** | 3.13+ | Installed automatically by UV |
| **UV** | Latest | `curl -LsSf https://astral.sh/uv/install.sh \| sh` |
| **Node.js** | 22+ | [nodejs.org](https://nodejs.org/) |
| **npm** | 10+ | Bundled with Node.js |
| **Docker** | 24+ | [docker.com](https://www.docker.com/) |
| **Docker Compose** | v2+ | Bundled with Docker Desktop |

## Quick Start

```bash
# Clone the repository
git clone https://github.com/christopherhouse/Azure-Integration-Copilot.git
cd Azure-Integration-Copilot

# Start both services with Docker Compose
make up
```

The backend will be available at `http://localhost:8000` and the frontend at `http://localhost:3000`.

## Project Structure

```
src/
├── backend/                  # Python 3.13 FastAPI backend
│   ├── main.py               # FastAPI app, middleware registration, health endpoints
│   ├── config.py             # pydantic-settings configuration (env vars / .env)
│   ├── middleware/
│   │   ├── auth.py           # Authentication middleware (stub — task 004)
│   │   ├── tenant_context.py # Tenant resolution middleware (stub — task 004)
│   │   └── quota.py          # Quota enforcement middleware (stub — task 004)
│   ├── shared/
│   │   ├── models.py         # ResponseEnvelope[T], PaginatedResponse[T], ErrorResponse
│   │   ├── exceptions.py     # AppError hierarchy (404, 401, 403, 422, 429)
│   │   ├── cosmos.py         # Cosmos DB async client wrapper
│   │   ├── blob.py           # Blob Storage async client wrapper
│   │   ├── events.py         # Event Grid publisher wrapper
│   │   └── logging.py        # structlog + OpenTelemetry setup
│   ├── domains/              # Domain modules (placeholder)
│   ├── pyproject.toml        # Python project config and dependencies
│   ├── uv.lock               # Locked dependency versions
│   └── Dockerfile            # Multi-stage production image
└── frontend/                 # Next.js 16 TypeScript frontend
    ├── src/
    │   ├── app/              # Next.js App Router pages
    │   │   ├── (auth)/       # Auth pages (login, callback)
    │   │   ├── (dashboard)/  # Dashboard layout and pages
    │   │   ├── api/auth/     # NextAuth.js API route
    │   │   └── v1/health/    # Frontend health check endpoint
    │   ├── components/
    │   │   ├── ui/           # shadcn/ui base components
    │   │   ├── layout/       # Sidebar, header, breadcrumbs
    │   │   └── providers/    # Auth, React Query, and realtime providers
    │   ├── hooks/            # Custom React hooks
    │   ├── lib/              # API client, auth config, utilities
    │   └── types/            # TypeScript type definitions
    ├── package.json          # Node.js project config
    └── Dockerfile            # Multi-stage production image

tests/
├── backend/                  # Python tests (pytest)
├── frontend/                 # Frontend tests (Jest + React Testing Library)
└── integration/              # End-to-end tests (placeholder)
```

## Backend Development

### Setup

```bash
cd src/backend

# Install dependencies (creates .venv automatically)
uv sync

# Start the development server with hot reload
uv run uvicorn main:app --reload --port 8000
```

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/api/v1/health` | Liveness probe — returns `200` when the process is running |
| `GET` | `/api/v1/health/ready` | Readiness probe — checks Cosmos DB connectivity |

### Configuration

The backend uses [pydantic-settings](https://docs.pydantic.dev/latest/concepts/pydantic_settings/) to load configuration from environment variables and an optional `.env` file in `src/backend/`.

| Variable | Default | Description |
|----------|---------|-------------|
| `ENVIRONMENT` | `development` | Runtime environment (`development`, `production`) |
| `COSMOS_DB_ENDPOINT` | *(empty)* | Cosmos DB account endpoint URL |
| `BLOB_STORAGE_ENDPOINT` | *(empty)* | Azure Blob Storage endpoint URL |
| `EVENT_GRID_NAMESPACE_ENDPOINT` | *(empty)* | Event Grid namespace endpoint URL |
| `EVENT_GRID_TOPIC` | `integration-events` | Event Grid topic name |
| `WEB_PUBSUB_ENDPOINT` | *(empty)* | Azure Web PubSub endpoint URL |
| `AZURE_CLIENT_ID` | *(empty)* | Managed identity client ID for Azure SDK authentication |
| `APPLICATIONINSIGHTS_CONNECTION_STRING` | *(empty)* | Application Insights connection string for telemetry export |
| `DEFENDER_SCAN_ENABLED` | `false` | Enable Microsoft Defender content scanning |

For local development, create a `.env` file in `src/backend/`:

```bash
# src/backend/.env (not committed to source control)
ENVIRONMENT=development
COSMOS_DB_ENDPOINT=https://your-cosmos-account.documents.azure.com:443/
```

> **Note**: All Azure service endpoints are optional for local development. The backend starts without them but the `/api/v1/health/ready` endpoint will return `503` until Cosmos DB is configured.

### API Response Format

All API responses follow a consistent envelope structure.

**Success responses** use `ResponseEnvelope`:

```json
{
  "data": { "status": "ok" },
  "meta": {
    "request_id": "550e8400-e29b-41d4-a716-446655440000",
    "timestamp": "2025-01-15T10:30:00Z"
  }
}
```

**Error responses** use `ErrorResponse`:

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "The requested resource was not found.",
    "detail": null,
    "request_id": "550e8400-e29b-41d4-a716-446655440000"
  }
}
```

Standard error codes:

| Code | HTTP Status | Thrown by |
|------|-------------|----------|
| `RESOURCE_NOT_FOUND` | 404 | `NotFoundError` |
| `UNAUTHORIZED` | 401 | `UnauthorizedError` |
| `FORBIDDEN` | 403 | `ForbiddenError` |
| `VALIDATION_ERROR` | 422 | `ValidationError` |
| `QUOTA_EXCEEDED` | 429 | `QuotaExceededError` |
| `INTERNAL_ERROR` | 500 | `AppError` (base) |

All error classes live in `src/backend/shared/exceptions.py` and are automatically converted to `ErrorResponse` JSON by the exception handler in `main.py`.

### Middleware Pipeline

Requests pass through three middleware layers before reaching the route handler:

```
Request → AuthMiddleware → TenantContextMiddleware → QuotaMiddleware → Route Handler
```

| Middleware | Sets on `request.state` | Status |
|------------|------------------------|--------|
| `AuthMiddleware` | `user_id` | Stub — hardcodes `dev-user-001`; skips health paths |
| `TenantContextMiddleware` | `tenant`, `tier` | Stub — hardcodes `dev-tenant-001` / `free` |
| `QuotaMiddleware` | *(none)* | Stub — passes through all requests |

> These middleware stubs will be replaced with real implementations in task 004.

### Observability

The backend integrates **structlog** for structured logging and **OpenTelemetry** for distributed tracing.

**Logging** — structlog is configured in `shared/logging.py`:
- **Development**: Colored console output for readability
- **Production** (`ENVIRONMENT=production`): JSON-formatted logs for ingestion by log aggregators
- All log entries include `trace_id` and `span_id` from OpenTelemetry for trace correlation

**Tracing** — OpenTelemetry is configured with:
- Automatic FastAPI request/response instrumentation
- Azure Monitor export via `azure-monitor-opentelemetry-exporter` (when `APPLICATIONINSIGHTS_CONNECTION_STRING` is set)
- Request IDs are propagated via the `X-Request-ID` header (auto-generated if absent)

### Linting

The backend uses [Ruff](https://docs.astral.sh/ruff/) for linting and formatting:

```bash
cd src/backend

# Check for lint errors
uv run ruff check .

# Auto-fix lint errors
uv run ruff check . --fix

# Format code
uv run ruff format .
```

Ruff is configured in `pyproject.toml`:

- **Target**: Python 3.13
- **Line length**: 120
- **Rules**: `E` (pycodestyle errors), `F` (pyflakes), `I` (isort), `UP` (pyupgrade), `B` (bugbear)

### Testing

```bash
cd src/backend

# Run all backend tests
uv run pytest

# Run with verbose output
uv run pytest -v

# Run a specific test file
uv run pytest ../../tests/backend/test_health.py
```

Tests are located in `tests/backend/` and use:

- **pytest** — Test framework
- **pytest-asyncio** — Async test support
- **httpx** — Async HTTP client for testing FastAPI endpoints

### Adding Dependencies

```bash
cd src/backend

# Add a production dependency
uv add <package-name>

# Add a dev dependency
uv add --group dev <package-name>

# Sync dependencies after editing pyproject.toml
uv sync
```

> **Important**: Always use UV for Python dependency management. Do not use `pip` directly.

## Frontend Development

### Setup

```bash
cd src/frontend

# Install dependencies
npm install

# Copy environment template
cp .env.local.example .env.local

# Start the development server with hot reload
npm run dev
```

The dev server starts at `http://localhost:3000`.

> **Note**: The `.env.local` file is **required** for authentication to work. Copy `.env.local.example` to `.env.local` before starting the dev server. The example file provides sensible defaults for local development.

### Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000` | Backend API base URL |
| `NEXTAUTH_URL` | `http://localhost:3000` | Frontend URL for NextAuth.js callbacks |
| `NEXTAUTH_SECRET` | *(required)* | Secret used to encrypt session tokens |

> **Note**: `NEXTAUTH_SECRET` and `NEXTAUTH_URL` are required to run the frontend. All defaults are pre-configured in `.env.local.example`.

### Available Scripts

| Script | Command | Description |
|--------|---------|-------------|
| `dev` | `npm run dev` | Start development server |
| `build` | `npm run build` | Build for production |
| `start` | `npm run start` | Start production server |
| `lint` | `npm run lint` | Run ESLint |
| `test` | `npm test` | Run Jest tests |

### Authentication

The frontend uses [NextAuth.js](https://next-auth.js.org/) for authentication with Azure AD B2C as the production provider.

**Development login**: In development mode (`NODE_ENV !== "production"`), a credentials provider (`dev-credentials`) allows login without a real B2C tenant. Enter any email address and password on the login page to sign in.

**Auth flow**:

1. Unauthenticated users are redirected to `/login`
2. After sign-in, the session includes an `accessToken`
3. The API client (`lib/api.ts`) automatically attaches the token as an `Authorization: Bearer` header
4. The dashboard layout guards all `/dashboard/*` routes — unauthenticated requests redirect to `/login`

**Session type**: The NextAuth session is augmented with an `accessToken` field (see `types/next-auth.d.ts`).

### Key Endpoints

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/v1/health` | Frontend health check — returns `{"status":"ok"}` |
| `HEAD` | `/v1/health` | Frontend health check — returns `200` with no body |
| `*` | `/api/auth/*` | NextAuth.js authentication endpoints |

> **Note**: These are frontend-specific endpoints served by Next.js. They are separate from the backend API endpoints under `/api/v1/`.

### Architecture

**Providers** — The root layout wraps the app in three nested providers:

1. **AuthProvider** — NextAuth.js `SessionProvider` for authentication state
2. **QueryProvider** — TanStack React Query with `staleTime: 30s`, `retry: 1`
3. **RealtimeProvider** — Stub for Azure Web PubSub (connected in a later task)

**API Client** — `lib/api.ts` exports `apiClient<T>(path, options?)`, a typed fetch wrapper that:

- Prepends `NEXT_PUBLIC_API_URL` to the path
- Attaches the session's `accessToken` as a Bearer token
- Parses JSON into `ResponseEnvelope<T>`
- Throws a typed `ApiError` on non-OK responses

**Dashboard Layout** — `(dashboard)/layout.tsx` provides a consistent shell with:

- Collapsible sidebar with navigation (Projects, Settings)
- Header with breadcrumbs and user menu
- Auth guard that redirects unauthenticated users to `/login`

### UI Components

The frontend uses [shadcn/ui](https://ui.shadcn.com/) with Tailwind CSS. To add a new component:

```bash
cd src/frontend
npx shadcn@latest add <component-name>
```

Components are installed to `src/components/ui/`.

### Testing

```bash
cd src/frontend

# Run all frontend tests
npm test

# Run with verbose output
npm test -- --verbose

# Run a specific test file
npm test -- --testPathPattern="page.test"
```

Tests are located in `tests/frontend/` and use:

- **Jest** — Test framework
- **React Testing Library** — Component testing utilities
- **@testing-library/jest-dom** — Custom DOM matchers

### Linting

```bash
cd src/frontend
npm run lint
```

ESLint is configured via `eslint.config.mjs` with the Next.js ESLint config.

## Docker Development

### Build and Run Both Services

```bash
# Build and start both services
docker compose up --build

# Run in detached mode
docker compose up --build -d

# Stop services
docker compose down
```

### Build Individual Services

```bash
# Backend only
docker compose build backend
docker compose up backend

# Frontend only
docker compose build frontend
docker compose up frontend
```

### Service Ports

| Service | Port | URL |
|---------|------|-----|
| Backend | 8000 | `http://localhost:8000` |
| Frontend | 3000 | `http://localhost:3000` |

## Makefile Targets

The root `Makefile` provides convenient shortcuts:

| Target | Description |
|--------|-------------|
| `make dev-backend` | Start backend dev server with hot reload |
| `make dev-frontend` | Start frontend dev server with hot reload |
| `make lint` | Run linters for both backend and frontend |
| `make test` | Run tests for both backend and frontend |
| `make build` | Build Docker images for both services |
| `make up` | Build and start both services with Docker Compose |

## CI/CD

### CI — `.github/workflows/ci.yml`

The CI workflow triggers on every PR targeting `main` and on pushes to `main`.

| Job | What it does |
|-----|------|
| **Frontend Build & Test** | Installs deps (`npm ci`), lints (ESLint), builds (Next.js), runs tests (Jest), publishes JUnit results |
| **Backend Build & Test** | Installs deps (`uv sync --frozen`), lints (Ruff), runs tests (pytest), publishes JUnit results |
| **Bicep Lint & Build** | Lints all Bicep templates, builds to ARM JSON, uploads compiled artifact |
| **Containers** | **Skipped on PRs.** Builds Docker images with Buildx, scans with [Trivy](https://github.com/aquasecurity/trivy) (SARIF → GitHub Security), pushes to GHCR on `main`, uploads container metadata JSON |

Container images are published to:
- `ghcr.io/<owner>/<repo>/frontend:<sha>`
- `ghcr.io/<owner>/<repo>/backend:<sha>`

On pushes to `main`, images are also tagged as `latest`.

### CD — `.github/workflows/cd.yml`

The CD workflow triggers via `workflow_run` when CI completes successfully on `main`. It deploys **dev → prod** sequentially — the prod stage is gated on dev success.

| Job | Environment | What it does |
|-----|-------------|------|
| **deploy-infra-dev** | dev | Deploys Bicep infrastructure via `az deployment group create` |
| **promote-containers-dev** | dev | Imports frontend/backend images from GHCR → dev ACR via `az acr import` |
| **deploy-apps-dev** | dev | Deploys `ca-frontend`, `ca-backend`, and `ca-worker` using `deploy-container-app.sh` |
| **deploy-infra-prod** | prod | Deploys Bicep infrastructure to prod |
| **promote-containers-prod** | prod | Imports frontend/backend images from GHCR → prod ACR |
| **deploy-apps-prod** | prod | Deploys Container Apps to prod using the deployment script |

### Running CI Locally

You can replicate the key CI steps locally:

```bash
# Frontend
cd src/frontend
npm ci
npm run lint
npm run build
npm test

# Backend
cd src/backend
uv sync --frozen
uv run ruff check .
uv run pytest -v

# Docker
docker compose build

# Bicep
az bicep build --file infra/bicep/main.bicep
```

## Technology Stack

| Component | Technology | Version |
|-----------|------------|---------|
| Backend framework | FastAPI | Latest |
| Backend runtime | Python | 3.13 |
| Backend package manager | UV | Latest |
| Backend linter | Ruff | Latest |
| Backend logging | structlog | Latest |
| Backend tracing | OpenTelemetry + Azure Monitor Exporter | Latest |
| Backend config | pydantic-settings | Latest |
| Frontend framework | Next.js | 16 |
| Frontend language | TypeScript | 5 |
| Frontend styling | Tailwind CSS | 4 |
| Frontend components | shadcn/ui | Latest |
| Frontend testing | Jest + React Testing Library | 29 |
| Backend testing | pytest + httpx | Latest |
| Containerization | Docker + Docker Compose | Latest |
