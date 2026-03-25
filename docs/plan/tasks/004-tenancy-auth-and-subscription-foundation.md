# Task 004 — Tenancy, Auth, and Subscription Foundation

## Title

Implement JWT authentication, tenant resolution, tier definitions, and quota enforcement middleware.

## Objective

Build the foundational multitenant services: JWT validation, tenant creation/resolution, user provisioning on first login, tier policy loading, and quota enforcement. After this task, every API request carries a validated tenant context with enforced usage limits.

## Why This Task Exists

Every domain operation (projects, artifacts, graph, analysis) requires:
1. A validated user identity (auth)
2. A resolved tenant context (tenancy)
3. Usage limits checked against the tenant's tier (quota)

This is the critical path before any feature can be built. Without it, domain tasks would need to fake or skip authorization.

## In Scope

- JWT validation middleware (Azure Entra ID B2C tokens)
- Tenant creation endpoint (`POST /api/v1/tenants`)
- Tenant retrieval endpoint (`GET /api/v1/tenants/me`)
- Tenant update endpoint (`PATCH /api/v1/tenants/me`)
- User auto-provisioning on first login
- Tenant context middleware (resolve tenant + tier from token)
- Tier definitions (free tier stored in code/config)
- Quota enforcement middleware
- QuotaService with check and increment functions
- Cosmos DB `tenants` container setup (tenant, user, tier_definition documents)
- Daily analysis count reset logic
- Tests for auth, tenant resolution, and quota enforcement

## Out of Scope

- Paid tier logic (designed, not built)
- Role-based authorization beyond single "owner" role
- Tenant invitation or member management
- SSO/SAML federation
- Frontend auth integration (task 003)
- Project or artifact endpoints

## Dependencies

- **Task 002** (API foundation): Middleware pipeline, Cosmos DB client wrapper, error handling, shared models.

## Files/Directories Expected to Be Created or Modified

```
src/backend/
├── middleware/
│   ├── auth.py                    # Real JWT validation (replace stub)
│   ├── tenant_context.py          # Real tenant resolution (replace stub)
│   └── quota.py                   # Real quota enforcement (replace stub)
├── shared/
│   └── models.py                  # Add TenantContext, UserContext types
├── domains/
│   └── tenants/
│       ├── __init__.py
│       ├── router.py              # Tenant CRUD routes
│       ├── service.py             # TenantService, UserService, TierService, QuotaService
│       ├── models.py              # Tenant, User, TierDefinition, QuotaResult Pydantic models
│       └── repository.py          # Cosmos DB operations for tenants container
tests/backend/
├── test_auth_middleware.py
├── test_tenant_context.py
├── test_quota_enforcement.py
└── test_tenant_routes.py
```

## Implementation Notes

### JWT Validation

```python
# middleware/auth.py
from jose import jwt, JWTError

class AuthMiddleware:
    def __init__(self, app, settings: Settings):
        self.app = app
        self.jwks_url = f"https://{settings.b2c_tenant}.b2clogin.com/{settings.b2c_tenant}.onmicrosoft.com/{settings.b2c_policy}/discovery/v2.0/keys"
        self.audience = settings.b2c_client_id

    async def __call__(self, scope, receive, send):
        # Skip auth for health endpoints
        if scope["path"].startswith("/api/v1/health"):
            await self.app(scope, receive, send)
            return
        
        # Extract and validate Bearer token
        # Set request.state.user_id and request.state.external_id
```

For local development, support a `SKIP_AUTH=true` environment variable that uses a hardcoded dev identity.

### Tenant Resolution

```python
# middleware/tenant_context.py
class TenantContextMiddleware:
    async def __call__(self, scope, receive, send):
        # Read user_id from request.state (set by auth middleware)
        # Look up user in Cosmos DB tenants container
        # Load tenant document
        # Load tier definition
        # Set request.state.tenant = TenantContext(...)
        # Set request.state.tier = TierDefinition(...)
```

### First-Login Auto-Provisioning

When the tenant context middleware cannot find a user for the external ID:
1. It does **not** auto-create. Instead, it returns 401 with a message indicating registration is needed.
2. The user calls `POST /api/v1/tenants` with their display name to create a tenant + user.
3. Subsequent requests resolve the tenant normally.

This explicit registration step avoids accidentally creating tenants for invalid tokens.

### Tier Definitions

Store tier definitions in code (not Cosmos DB) for MVP:

```python
FREE_TIER = TierDefinition(
    id="tier_free",
    name="Free",
    slug="free",
    limits=TierLimits(
        max_projects=3,
        max_artifacts_per_project=25,
        max_total_artifacts=50,
        max_file_size_mb=10,
        max_daily_analyses=20,
        max_concurrent_analyses=1,
        max_graph_components_per_project=500,
    ),
    features=TierFeatures(
        realtime_notifications=True,
        agent_analysis=True,
        custom_agent_prompts=False,
        export_graph=False,
    ),
)
```

### Quota Enforcement Middleware

```python
# middleware/quota.py
QUOTA_RULES = {
    ("POST", "/api/v1/projects"): [QuotaCheck("max_projects", "project_count")],
    ("POST", r"/api/v1/projects/.+/artifacts"): [
        QuotaCheck("max_artifacts_per_project", "artifact_count", scope="project"),
        QuotaCheck("max_total_artifacts", "total_artifact_count"),
    ],
    ("POST", r"/api/v1/projects/.+/analyses"): [
        QuotaCheck("max_daily_analyses", "daily_analysis_count"),
    ],
}
```

The middleware matches the request method and path against `QUOTA_RULES`. For matching rules, it calls `QuotaService.check()`. If any check fails, return 429.

### Usage Counter Updates

Usage counters on the tenant document are updated after successful operations (not by the middleware). For example, after `POST /projects` succeeds, the service increments `tenant.usage.project_count`.

Use Cosmos DB conditional updates (ETags) to handle concurrent counter increments.

### Daily Analysis Reset

```python
def check_daily_analysis_quota(tenant: Tenant, tier: TierDefinition) -> QuotaResult:
    now = datetime.utcnow()
    if now >= tenant.usage.daily_analysis_reset_at:
        # Reset counter
        tenant.usage.daily_analysis_count = 0
        tenant.usage.daily_analysis_reset_at = next_midnight_utc()
    return check_quota(tenant.usage.daily_analysis_count, tier.limits.max_daily_analyses)
```

## Acceptance Criteria

- [ ] Requests without a Bearer token return 401
- [ ] Requests with an invalid token return 401
- [ ] `POST /api/v1/tenants` creates a new tenant and user
- [ ] `GET /api/v1/tenants/me` returns the current tenant with usage data
- [ ] `PATCH /api/v1/tenants/me` updates the tenant display name
- [ ] `request.state.tenant` is populated for authenticated requests
- [ ] `request.state.tier` is populated with the free tier definition
- [ ] Quota middleware returns 429 when a limit is exceeded
- [ ] 429 response includes the limit name, current usage, and max
- [ ] Daily analysis count resets at midnight UTC
- [ ] Health endpoints remain accessible without auth
- [ ] Tests pass for auth, tenant resolution, and quota enforcement

## Definition of Done

- Auth middleware validates JWTs (or skips in dev mode).
- Tenant context is available in all route handlers.
- Quota enforcement blocks requests that exceed limits.
- Tenant CRUD endpoints work end-to-end.
- Domain tasks can rely on `request.state.tenant` and `request.state.tier` being present.

## Risks / Gotchas

- **B2C configuration**: Real JWT validation requires B2C tenant details. Support `SKIP_AUTH=true` for local development.
- **Token claims**: B2C tokens may have different claim structures than standard Entra ID tokens. Verify the `oid` (object ID) claim is present.
- **Concurrent quota updates**: Cosmos DB ETag-based conditional updates may cause retries under high concurrency. Acceptable for MVP.
- **Cosmos DB container creation**: The `tenants` container must be created before first use. Handle this in application startup or separately.

## Suggested Validation Steps

1. Start the API with `SKIP_AUTH=true` for development testing.
2. Call `POST /api/v1/tenants` with `{ "displayName": "Test Tenant" }` → verify 201 response.
3. Call `GET /api/v1/tenants/me` → verify tenant with usage data.
4. Attempt to exceed a quota (e.g., create more projects than allowed) → verify 429 response.
5. Run tests: `uv run pytest tests/backend/test_auth*.py tests/backend/test_tenant*.py tests/backend/test_quota*.py -v`
6. Verify structured logs include `tenantId` for authenticated requests.
