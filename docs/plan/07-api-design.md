# 07 — API Design

## Goals

- Define the API as one FastAPI service with modular domain boundaries.
- Provide route groups and endpoint list.
- Define request/response contract guidance.
- Define auth and authorization patterns.
- Define quota enforcement points.
- Define validation and error response patterns.
- Define internal module boundaries.

## Scope

MVP: all endpoints needed for project management, artifact upload, graph queries, analysis, and realtime token negotiation.

---

## API Architecture

### Modular Monolith

The API is a single FastAPI application composed of domain modules. Each module owns its routes, services, and data access. Modules communicate through shared services (e.g., `TenantContext`, `QuotaService`), not HTTP calls.

```
src/backend/
├── main.py                    # FastAPI app entry point, router registration
├── config.py                  # Settings and environment config
├── middleware/
│   ├── auth.py                # JWT validation, user identity extraction
│   ├── tenant_context.py      # Tenant + tier resolution
│   └── quota.py               # Quota enforcement middleware
├── shared/
│   ├── models.py              # Shared Pydantic models (IDs, pagination, errors)
│   ├── cosmos.py              # Cosmos DB client wrapper
│   ├── blob.py                # Blob Storage client wrapper
│   ├── events.py              # Event Grid publisher
│   ├── pubsub.py              # Web PubSub token generation
│   └── exceptions.py          # Application exception classes
├── domains/
│   ├── tenants/
│   │   ├── router.py          # Tenant routes
│   │   ├── service.py         # TenantService, UserService
│   │   ├── models.py          # Tenant/User Pydantic models
│   │   └── repository.py      # Cosmos DB operations for tenants
│   ├── projects/
│   │   ├── router.py          # Project routes
│   │   ├── service.py         # ProjectService
│   │   ├── models.py          # Project Pydantic models
│   │   └── repository.py      # Cosmos DB operations for projects
│   ├── artifacts/
│   │   ├── router.py          # Artifact routes
│   │   ├── service.py         # ArtifactService (upload, status)
│   │   ├── models.py          # Artifact Pydantic models
│   │   └── repository.py      # Cosmos DB + Blob operations for artifacts
│   ├── graph/
│   │   ├── router.py          # Graph query routes
│   │   ├── service.py         # GraphService
│   │   ├── models.py          # Component/Edge/Summary models
│   │   └── repository.py      # Cosmos DB graph queries
│   ├── analysis/
│   │   ├── router.py          # Analysis routes
│   │   ├── service.py         # AnalysisService
│   │   ├── models.py          # Analysis Pydantic models
│   │   └── repository.py      # Cosmos DB operations for analyses
│   └── realtime/
│       ├── router.py          # Web PubSub token negotiation
│       └── service.py         # RealtimeService
└── workers/                   # Worker entry points (separate from API)
    ├── scan_gate/
    ├── parser/
    ├── graph_builder/
    ├── analysis/
    └── notification/
```

### Module Boundaries

- Each domain module has its own `router.py`, `service.py`, `models.py`, and `repository.py`.
- Modules **may** import from `shared/` but **must not** import from each other's internals.
- Cross-domain queries (e.g., "list artifacts for a project") are handled within the module that owns the route, querying the relevant Cosmos DB container directly.
- If two modules need to coordinate, they do so through events or shared services, not direct imports.

---

## Route Groups and Endpoints

### Tenants

| Method | Path | Description | Auth | Quota |
|--------|------|-------------|------|-------|
| `POST` | `/api/v1/tenants` | Create tenant (first-login) | Token | — |
| `GET` | `/api/v1/tenants/me` | Get current tenant | Token | — |
| `PATCH` | `/api/v1/tenants/me` | Update tenant display name | Token + Owner | — |

### Projects

| Method | Path | Description | Auth | Quota |
|--------|------|-------------|------|-------|
| `POST` | `/api/v1/projects` | Create project | Token | `maxProjects` |
| `GET` | `/api/v1/projects` | List projects | Token | — |
| `GET` | `/api/v1/projects/{projectId}` | Get project | Token | — |
| `PATCH` | `/api/v1/projects/{projectId}` | Update project | Token | — |
| `DELETE` | `/api/v1/projects/{projectId}` | Soft-delete project | Token + Owner | — |

### Artifacts

| Method | Path | Description | Auth | Quota |
|--------|------|-------------|------|-------|
| `POST` | `/api/v1/projects/{projectId}/artifacts` | Upload artifact (multipart) | Token | `maxArtifactsPerProject`, `maxTotalArtifacts`, `maxFileSizeMb` |
| `GET` | `/api/v1/projects/{projectId}/artifacts` | List artifacts | Token | — |
| `GET` | `/api/v1/projects/{projectId}/artifacts/{artifactId}` | Get artifact metadata | Token | — |
| `GET` | `/api/v1/projects/{projectId}/artifacts/{artifactId}/download` | Download raw artifact | Token | — |
| `DELETE` | `/api/v1/projects/{projectId}/artifacts/{artifactId}` | Soft-delete artifact | Token | — |

### Graph

| Method | Path | Description | Auth | Quota |
|--------|------|-------------|------|-------|
| `GET` | `/api/v1/projects/{projectId}/graph/summary` | Get graph summary | Token | — |
| `GET` | `/api/v1/projects/{projectId}/graph/components` | List components (paginated) | Token | — |
| `GET` | `/api/v1/projects/{projectId}/graph/components/{componentId}` | Get component details | Token | — |
| `GET` | `/api/v1/projects/{projectId}/graph/components/{componentId}/neighbors` | Get neighbors | Token | — |
| `GET` | `/api/v1/projects/{projectId}/graph/edges` | List edges (paginated) | Token | — |

### Analysis

| Method | Path | Description | Auth | Quota |
|--------|------|-------------|------|-------|
| `POST` | `/api/v1/projects/{projectId}/analyses` | Request analysis | Token | `maxDailyAnalyses`, `maxConcurrentAnalyses` |
| `GET` | `/api/v1/projects/{projectId}/analyses` | List analyses | Token | — |
| `GET` | `/api/v1/projects/{projectId}/analyses/{analysisId}` | Get analysis result | Token | — |

### Realtime

| Method | Path | Description | Auth | Quota |
|--------|------|-------------|------|-------|
| `POST` | `/api/v1/realtime/negotiate` | Get Web PubSub client token | Token | — |

### Health

| Method | Path | Description | Auth | Quota |
|--------|------|-------------|------|-------|
| `GET` | `/api/v1/health` | Health check | None | — |
| `GET` | `/api/v1/health/ready` | Readiness check (DB connectivity) | None | — |

---

## Request/Response Contract Guidance

### Standard Response Envelope

All successful responses use a consistent envelope:

```json
{
  "data": { ... },
  "meta": {
    "requestId": "req_01HQ...",
    "timestamp": "2026-03-25T14:30:00Z"
  }
}
```

### Paginated Response

```json
{
  "data": [ ... ],
  "meta": {
    "requestId": "req_01HQ...",
    "timestamp": "2026-03-25T14:30:00Z"
  },
  "pagination": {
    "page": 1,
    "pageSize": 20,
    "totalCount": 47,
    "totalPages": 3,
    "hasNextPage": true
  }
}
```

### Standard Pagination Parameters

| Parameter | Type | Default | Max |
|-----------|------|---------|-----|
| `page` | int | 1 | — |
| `pageSize` | int | 20 | 100 |

### ID Format

All resource IDs use ULID with a type prefix:
- `tn_` for tenants
- `usr_` for users
- `prj_` for projects
- `art_` for artifacts
- `cmp_` for components
- `edg_` for edges
- `anl_` for analyses
- `evt_` for events

---

## Auth and Authorization

### Authentication

1. All API requests (except `/health`) require a valid JWT in the `Authorization: Bearer <token>` header.
2. The JWT is issued by Azure Entra ID (B2C for external users).
3. The `auth` middleware validates the token signature, expiry, and audience.
4. The middleware extracts:
   - `sub` (Entra object ID) → mapped to internal user ID
   - `tid` or custom claim → mapped to tenant ID

### Authorization

1. The `tenant_context` middleware loads the tenant and tier from Cosmos DB.
2. All route handlers receive the resolved tenant context via `request.state.tenant`.
3. Authorization is currently single-role (owner). Future roles will require per-endpoint role checks.
4. Every Cosmos DB query includes the tenant ID from the request context. No query runs without tenant scoping.

### Token Flow

```
Browser → Entra ID B2C login → ID token + access token
Browser → API with access token in Authorization header
API → Validate token → Resolve tenant → Process request
```

---

## Quota Enforcement Points

| Endpoint | Limit | Enforcement |
|----------|-------|-------------|
| `POST /projects` | `maxProjects` | Middleware checks `tenant.usage.projectCount` |
| `POST /projects/{id}/artifacts` | `maxArtifactsPerProject` | Middleware checks artifact count for project |
| `POST /projects/{id}/artifacts` | `maxTotalArtifacts` | Middleware checks `tenant.usage.totalArtifactCount` |
| `POST /projects/{id}/artifacts` | `maxFileSizeMb` | Middleware checks `Content-Length` header |
| `POST /projects/{id}/analyses` | `maxDailyAnalyses` | Middleware checks `tenant.usage.dailyAnalysisCount` |
| `POST /projects/{id}/analyses` | `maxConcurrentAnalyses` | Middleware checks in-progress analysis count |

### Quota Exceeded Response

```
HTTP 429 Too Many Requests
Retry-After: 3600

{
  "error": {
    "code": "QUOTA_EXCEEDED",
    "message": "Daily analysis limit reached (20/20)",
    "detail": {
      "limit": "maxDailyAnalyses",
      "current": 20,
      "max": 20,
      "resetsAt": "2026-03-26T00:00:00Z"
    }
  }
}
```

---

## Validation and Error Response Patterns

### Validation

- Use Pydantic models for all request body and query parameter validation.
- Return `422 Unprocessable Entity` for validation errors (FastAPI default).
- Custom validators for business rules (e.g., project name length, artifact type).

### Error Response Format

```json
{
  "error": {
    "code": "RESOURCE_NOT_FOUND",
    "message": "Project not found",
    "detail": {
      "resourceType": "project",
      "resourceId": "prj_01HQ..."
    },
    "requestId": "req_01HQ..."
  }
}
```

### Standard Error Codes

| HTTP Status | Error Code | Description |
|-------------|-----------|-------------|
| 400 | `BAD_REQUEST` | Malformed request |
| 401 | `UNAUTHORIZED` | Missing or invalid token |
| 403 | `FORBIDDEN` | Valid token but insufficient permissions |
| 404 | `RESOURCE_NOT_FOUND` | Resource does not exist or belongs to another tenant |
| 409 | `CONFLICT` | Resource already exists (e.g., duplicate project name) |
| 413 | `FILE_TOO_LARGE` | Upload exceeds `maxFileSizeMb` |
| 422 | `VALIDATION_ERROR` | Request body fails validation |
| 429 | `QUOTA_EXCEEDED` | Tier limit reached |
| 500 | `INTERNAL_ERROR` | Unexpected server error |

### Security: No Tenant Leakage in Errors

- If a resource exists but belongs to a different tenant, return `404 RESOURCE_NOT_FOUND`, not `403 FORBIDDEN`.
- Error messages must never include other tenant IDs or data.

---

## Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| Framework | FastAPI | Async, Pydantic integration, OpenAPI auto-generation |
| API style | REST with resource-oriented routes | Standard, well-understood, good tooling |
| Versioning | URL path (`/api/v1/`) | Explicit, easy to route, clear in logs |
| Response envelope | Consistent `{ data, meta }` wrapper | Predictable client parsing |
| Error format | `{ error: { code, message, detail } }` | Machine-readable codes + human-readable messages |
| Pagination | Offset-based (`page`, `pageSize`) | Simple, sufficient for MVP query volumes |

## Assumptions

- FastAPI's built-in OpenAPI generation is used for API documentation.
- Pydantic v2 is used for all models.
- The API runs behind App Gateway; it does not handle TLS directly.

## Constraints

- All endpoints must be tenant-scoped (except health checks).
- No direct database access from route handlers; all access goes through repository classes.
- Workers do not expose HTTP endpoints; they are not part of the API.
