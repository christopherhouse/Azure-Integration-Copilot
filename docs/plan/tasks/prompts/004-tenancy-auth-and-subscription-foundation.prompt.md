# Prompt — Execute Task 004: Tenancy, Auth, and Subscription Foundation

You are an expert Python backend engineer. Execute the following task to implement the multitenant authentication and authorization foundation for Integrisight.ai.

## Context

Read these documents before starting:

- **Task spec**: `docs/plan/tasks/004-tenancy-auth-and-subscription-foundation.md`
- **Tenancy domain**: `docs/plan/02-domain-tenancy-and-subscriptions.md`
- **API design**: `docs/plan/07-api-design.md`
- **Security**: `docs/plan/09-security-networking-and-ops.md`

**Prerequisite**: Task 002 (API foundation) must be complete. The middleware pipeline, Cosmos DB client wrapper, error handling, and shared models must exist.

## What You Must Do

Replace the middleware stubs from task 002 with real JWT validation, tenant resolution, tier definitions, and quota enforcement. Build the tenant domain module with CRUD endpoints.

### Step 1 — Tenant Domain Models

Create `src/backend/domains/tenants/models.py` with Pydantic v2 models:
- `TierLimits` — max_projects (3), max_artifacts_per_project (25), max_total_artifacts (50), max_file_size_mb (10), max_daily_analyses (20), max_concurrent_analyses (1), max_graph_components_per_project (500)
- `TierFeatures` — realtime_notifications (True), agent_analysis (True), custom_agent_prompts (False), export_graph (False)
- `TierDefinition` — id, name, slug, limits: TierLimits, features: TierFeatures
- `Usage` — project_count, total_artifact_count, daily_analysis_count, daily_analysis_reset_at
- `Tenant` — id, partition_key, type ("tenant"), display_name, owner_id, tier_id, status, usage, created_at, updated_at
- `User` — id, partition_key, type ("user"), tenant_id, external_id, email, display_name, role ("owner"), status, created_at
- `CreateTenantRequest` — display_name (str, required)
- `TenantResponse`, `QuotaResult` — as needed

Define the `FREE_TIER` constant as a `TierDefinition` with the limits above.

### Step 2 — Tenant Repository

Create `src/backend/domains/tenants/repository.py`:
- Cosmos DB operations for the `tenants` container (partition key: `tenantId`)
- `create_tenant()`, `get_tenant()`, `update_tenant()`, `create_user()`, `get_user_by_external_id()`, `increment_usage()`, `reset_daily_analysis_count()`
- All operations are tenant-scoped.

### Step 3 — Tenant Service

Create `src/backend/domains/tenants/service.py`:
- `TenantService` — create tenant + user on registration, get tenant, update tenant
- `UserService` — get or create user by external ID
- `TierService` — resolve tier definition for a tenant (returns `FREE_TIER` for MVP)
- `QuotaService` — `check(tenant, tier, limit_name)` → `QuotaResult`, daily reset logic

### Step 4 — Auth Middleware (Real)

Replace `src/backend/middleware/auth.py`:
- Validate JWT tokens from Azure Entra ID B2C using `python-jose` (add to dependencies).
- Fetch JWKS from B2C discovery endpoint.
- Extract `oid` (object ID) from token claims → `request.state.external_id`.
- Skip auth for paths starting with `/api/v1/health`.
- Support `SKIP_AUTH=true` env var for development (set hardcoded dev identity).

### Step 5 — Tenant Context Middleware (Real)

Replace `src/backend/middleware/tenant_context.py`:
- Look up user by `request.state.external_id` in Cosmos DB.
- If user found: load tenant, load tier → set `request.state.tenant` and `request.state.tier`.
- If user not found: allow only `POST /api/v1/tenants` (registration); return 401 for other routes.

### Step 6 — Quota Enforcement Middleware (Real)

Replace `src/backend/middleware/quota.py`:
- Match request method + path against quota rules:
  - `POST /api/v1/projects` → check `max_projects` vs `project_count`
  - `POST /projects/{id}/artifacts` → check `max_artifacts_per_project` and `max_total_artifacts`
  - `POST /projects/{id}/analyses` → check `max_daily_analyses`
- On quota exceeded: return 429 with limit name, current usage, and max.
- Reset daily analysis count if past `daily_analysis_reset_at`.

### Step 7 — Tenant Routes

Create `src/backend/domains/tenants/router.py`:
- `POST /api/v1/tenants` — create tenant + user (registration endpoint). Returns 201.
- `GET /api/v1/tenants/me` — return current tenant with usage data.
- `PATCH /api/v1/tenants/me` — update tenant display_name.

Register the tenant router in `main.py`.

### Step 8 — Tests

Create tests under `tests/backend/`:
- `test_auth_middleware.py` — test that missing/invalid tokens return 401, valid tokens set state.
- `test_tenant_context.py` — test tenant resolution and first-login flow.
- `test_quota_enforcement.py` — test that quota limits return 429 with correct response body.
- `test_tenant_routes.py` — test tenant CRUD endpoints.

### Step 9 — Validation

1. Start the API with `SKIP_AUTH=true`.
2. `POST /api/v1/tenants` with `{ "displayName": "Test Tenant" }` → 201 with tenant data.
3. `GET /api/v1/tenants/me` → returns tenant with usage object.
4. `PATCH /api/v1/tenants/me` with `{ "displayName": "Updated" }` → updated tenant.
5. Verify `request.state.tenant` and `request.state.tier` are populated in subsequent requests.
6. Run tests: `uv run pytest tests/backend/ -v`
7. Run linter: `uv run ruff check src/backend/`

## Constraints

- JWT validation must support `SKIP_AUTH=true` for local development.
- Tier definitions are stored in code, not Cosmos DB.
- Only the "owner" role exists for MVP — do not implement role-based checks.
- Usage counters are updated after successful operations, not by the middleware.
- Use Cosmos DB ETags for concurrent counter updates.
- Do not build project or artifact endpoints — those are task 005.

## Done When

- Auth middleware validates JWTs (or skips in dev mode).
- Tenant context is available via `request.state.tenant` in all route handlers.
- Quota enforcement returns 429 when limits are exceeded.
- Tenant CRUD endpoints work end-to-end.
- All tests pass.
