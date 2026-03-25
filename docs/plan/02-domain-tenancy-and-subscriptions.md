# 02 — Domain: Tenancy and Subscriptions

## Goals

- Define the tenant data model and lifecycle.
- Define user roles within a tenant.
- Define the subscription tier model and policy-based enforcement.
- Define tenant isolation rules that apply across every layer of the system.

## Scope

MVP includes: tenant creation, single-owner role, free tier only, quota enforcement middleware.

Future: additional roles (member, viewer), paid tiers, tenant invitations, SSO federation.

---

## Tenant Model

A **tenant** is the top-level organizational boundary. All data — projects, artifacts, graph, analyses — belongs to exactly one tenant.

### Tenant Entity

```json
{
  "id": "tn_01HQXYZ...",
  "partitionKey": "tn_01HQXYZ...",
  "type": "tenant",
  "displayName": "Contoso Integration Team",
  "ownerId": "usr_01HQABC...",
  "tierId": "free",
  "status": "active",
  "usage": {
    "projectCount": 2,
    "totalArtifactCount": 12,
    "dailyAnalysisCount": 5,
    "dailyAnalysisResetAt": "2026-03-26T00:00:00Z"
  },
  "createdAt": "2026-03-20T10:00:00Z",
  "updatedAt": "2026-03-25T14:30:00Z"
}
```

### Tenant ID Format

- Prefix: `tn_`
- Body: ULID (sortable, unique, no collisions)
- Example: `tn_01HQXYZ9K8P7N6M5Q4R3`

### Tenant Status

| Status | Description |
|--------|-------------|
| `active` | Normal operation |
| `suspended` | Quota exceeded or admin action; read-only access |
| `deleted` | Soft-deleted; data retained for 30 days then purged |

---

## User Model

### User Entity

```json
{
  "id": "usr_01HQABC...",
  "partitionKey": "tn_01HQXYZ...",
  "type": "user",
  "tenantId": "tn_01HQXYZ...",
  "externalId": "oid-from-entra-token",
  "email": "alice@contoso.com",
  "displayName": "Alice",
  "role": "owner",
  "status": "active",
  "createdAt": "2026-03-20T10:00:00Z"
}
```

### Roles (MVP)

| Role | Permissions |
|------|-------------|
| `owner` | Full CRUD on all tenant resources. Manage tenant settings. |

### Roles (Future)

| Role | Permissions |
|------|-------------|
| `member` | CRUD on projects and artifacts. Run analyses. Cannot manage tenant. |
| `viewer` | Read-only access to projects, artifacts, graph, and analyses. |

---

## Subscription Tier Model

### Tier Definition Entity

Tier definitions are stored as configuration, not per-tenant data. They define the policy that is evaluated at enforcement points.

```json
{
  "id": "tier_free",
  "type": "tier_definition",
  "name": "Free",
  "slug": "free",
  "limits": {
    "maxProjects": 3,
    "maxArtifactsPerProject": 25,
    "maxTotalArtifacts": 50,
    "maxFileSizeMb": 10,
    "maxDailyAnalyses": 20,
    "maxConcurrentAnalyses": 1,
    "maxGraphComponentsPerProject": 500
  },
  "features": {
    "realtimeNotifications": true,
    "agentAnalysis": true,
    "customAgentPrompts": false,
    "exportGraph": false
  }
}
```

### Tier Definitions (MVP + Future Placeholders)

| Limit / Feature | Free (MVP) | Pro (Future) | Enterprise (Future) |
|-----------------|------------|-------------|-------------------|
| Max projects | 3 | 20 | Unlimited |
| Max artifacts per project | 25 | 100 | 500 |
| Max total artifacts | 50 | 500 | 5000 |
| Max file size (MB) | 10 | 50 | 100 |
| Max daily analyses | 20 | 100 | Unlimited |
| Max concurrent analyses | 1 | 3 | 10 |
| Max graph components/project | 500 | 5000 | 50000 |
| Realtime notifications | ✅ | ✅ | ✅ |
| Agent analysis | ✅ | ✅ | ✅ |
| Custom agent prompts | ❌ | ✅ | ✅ |
| Export graph | ❌ | ✅ | ✅ |

---

## Quota and Policy Enforcement

### Enforcement Approach

Quotas are enforced at well-defined enforcement points, not scattered through business logic.

```
Request → Auth Middleware → Tenant Context Middleware → Quota Middleware → Route Handler
```

1. **Auth Middleware** — Validates the JWT, extracts user identity.
2. **Tenant Context Middleware** — Resolves the tenant from the token, loads tenant + tier into request context.
3. **Quota Middleware** — For write operations, checks the relevant limit against current usage. Returns `429 Too Many Requests` with a `Retry-After` header if exceeded.

### Quota Check Function (Pseudocode)

```python
def check_quota(tenant: Tenant, tier: TierDefinition, resource: str, increment: int = 1) -> QuotaResult:
    current = tenant.usage[resource]
    limit = tier.limits[resource]
    if current + increment > limit:
        return QuotaResult(allowed=False, current=current, limit=limit)
    return QuotaResult(allowed=True, current=current, limit=limit)
```

### Enforcement Points

| Operation | Limit Checked | Enforcement Point |
|-----------|--------------|-------------------|
| Create project | `maxProjects` | API middleware |
| Upload artifact | `maxArtifactsPerProject`, `maxTotalArtifacts`, `maxFileSizeMb` | API middleware |
| Request analysis | `maxDailyAnalyses`, `maxConcurrentAnalyses` | API middleware |
| Graph build | `maxGraphComponentsPerProject` | Worker pre-check |

### Daily Reset

- `dailyAnalysisCount` resets at midnight UTC.
- `dailyAnalysisResetAt` tracks the next reset time.
- The API checks: if `now >= dailyAnalysisResetAt`, reset the counter before evaluating the quota.

---

## Tenant Isolation Rules

Tenant isolation is enforced at every layer, not just the API.

### API Layer

- Every request is scoped to a tenant via the auth token.
- All Cosmos DB queries include the tenant ID in the partition key or a WHERE clause.
- No API endpoint allows cross-tenant data access.

### Storage Layer (Blob)

- Blob paths are prefixed with the tenant ID: `tenants/{tenantId}/projects/{projectId}/artifacts/{artifactId}/{filename}`
- Blob access is through the API backend using managed identity; no direct user access to Blob Storage.
- SAS tokens are never issued to end users.

### Storage Layer (Cosmos DB)

- All containers use a partition key strategy that includes the tenant ID.
- Cross-partition queries are avoided by design (queries always include tenant scope).
- Container-level RBAC is not used; tenant isolation is enforced at the application level.

### Eventing Layer (Event Grid)

- All events include `tenantId` in the event data.
- Workers filter/validate the tenant ID on every event they process.
- A single Event Grid topic is shared; isolation is at the data level, not the topic level.

### Notification Layer (Web PubSub)

- Web PubSub groups are scoped: `tenant:{tenantId}`, `project:{tenantId}:{projectId}`.
- The API issues Web PubSub client tokens scoped to the user's tenant groups only.
- No user can join a group belonging to another tenant.

### Agent Layer (Foundry)

- All tool invocations receive `tenantId` and `projectId` as required parameters.
- Tools query Cosmos DB with tenant/project scope; they cannot return cross-tenant data.
- The agent system prompt includes the tenant and project context.

---

## Foundational Multitenant Services (MVP)

These services must be implemented before any domain feature:

| Service | Responsibility |
|---------|---------------|
| `TenantService` | CRUD for tenant entities; tenant resolution from token |
| `UserService` | User creation on first login; role lookup |
| `TierService` | Load tier definitions; resolve tier for a tenant |
| `QuotaService` | Check and increment usage counters; daily reset logic |
| `TenantContextMiddleware` | FastAPI middleware that populates `request.state.tenant` and `request.state.tier` |
| `QuotaMiddleware` | FastAPI middleware that enforces limits on write operations |

---

## Cosmos DB Storage

Tenancy-related documents are stored in the `tenants` container. See [04-domain-graph-and-metadata.md](04-domain-graph-and-metadata.md) for the full container strategy including `projects`, `graph`, and `analyses` containers.

| Document Type | Partition Key | Example |
|---------------|--------------|---------|
| `tenant` | `{tenantId}` | Tenant metadata + usage |
| `user` | `{tenantId}` | User within a tenant |
| `tier_definition` | `"tier_definitions"` | Tier policy (small set, single partition) |

---

## Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| Tenant isolation level | Application-level | Simpler than DB-per-tenant; sufficient for MVP; Cosmos DB partition key scoping is efficient |
| Tier enforcement | Middleware + central QuotaService | Avoids scattered conditionals; single place to modify limits |
| ID format | ULID with type prefix | Sortable, unique, human-readable type prefix aids debugging |
| Daily quota reset | UTC midnight | Simple, predictable, timezone-neutral |

## Assumptions

- A single Cosmos DB account is shared across all tenants (serverless mode).
- Usage counters can tolerate slight inaccuracy under concurrent writes (last-writer-wins is acceptable for MVP).
- Tenant creation happens as part of first-login flow.

## Open Questions

| # | Question |
|---|----------|
| 1 | Should the free tier have a tenant-level storage quota (total MB) in addition to artifact counts? |
| 2 | What is the soft-delete retention period before hard purge? (Proposed: 30 days) |
