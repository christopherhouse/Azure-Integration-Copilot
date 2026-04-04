# 10 — Implementation Plan

## Goals

- Provide a phased implementation plan in execution order.
- Define dependencies between phases.
- Define acceptance criteria per phase.
- Provide a recommended build order for a coding agent.
- List anti-goals to prevent overengineering.
- Describe how to execute this plan with an AI coding agent.

## Scope

This plan covers MVP implementation from monorepo scaffold to end-to-end working system.

---

## Phases Overview

| Phase | Name | Dependencies | Duration Estimate |
|-------|------|-------------|-------------------|
| 1 | Monorepo Scaffold | None | 1 task |
| 2 | API Foundation | Phase 1 | 1 task |
| 3 | Frontend Foundation | Phase 1 | 1 task (parallelizable with Phase 2) |
| 4 | Tenancy, Auth, and Subscription Foundation | Phase 2 | 1 task |
| 5 | Project and Artifact Domain | Phase 4 | 1 task |
| 6 | Upload Flow and Storage | Phase 5 | 1 task |
| 7 | Eventing Foundation | Phase 2 | 1 task (parallelizable with Phases 5–6) |
| 8 | Parser Worker | Phases 6, 7 | 1 task |
| 9 | Graph Builder and Persistence | Phase 8 | 1 task |
| 10 | Foundry Agent, Tools, and Analysis Flow | Phases 7, 9 | 1 task |

### Dependency Graph

```
Phase 1: Monorepo Scaffold
  ├── Phase 2: API Foundation
  │     ├── Phase 4: Tenancy + Auth + Subscriptions
  │     │     └── Phase 5: Projects + Artifacts
  │     │           └── Phase 6: Upload Flow + Storage
  │     │                 └── Phase 8: Parser Worker ──┐
  │     │                                              │
  │     └── Phase 7: Eventing Foundation ──────────────┤
  │                                                    │
  │                                    Phase 9: Graph Builder ─── Phase 10: Agent + Analysis
  │
  └── Phase 3: Frontend Foundation
```

---

## Phase 1: Monorepo Scaffold

**Task:** [001-monorepo-scaffold.md](tasks/001-monorepo-scaffold.md)

**What gets built:**
- Monorepo directory structure
- Python project setup (pyproject.toml, UV lock)
- Next.js project setup
- Shared configuration (linting, formatting)
- Docker development setup
- CI/CD skeleton

**Acceptance Criteria:**
- [ ] `uv sync` succeeds for the backend
- [ ] `npm install` succeeds for the frontend
- [ ] `npm run dev` starts the Next.js dev server
- [ ] `uvicorn` starts the FastAPI dev server
- [ ] Linting passes for both projects
- [ ] Docker compose brings up both services

---

## Phase 2: API Foundation

**Task:** [002-api-foundation.md](tasks/002-api-foundation.md)

**What gets built:**
- FastAPI application skeleton
- Health endpoints
- Error handling middleware
- Request/response envelope
- Shared models and utilities
- Cosmos DB client wrapper
- Blob Storage client wrapper
- Event Grid publisher wrapper

**Acceptance Criteria:**
- [ ] `GET /api/v1/health` returns 200
- [ ] `GET /api/v1/health/ready` checks Cosmos DB connectivity
- [ ] Error responses follow the standard format
- [ ] Pydantic models compile with strict mode
- [ ] Azure SDK clients initialize with `DefaultAzureCredential`

---

## Phase 3: Frontend Foundation

**Task:** [003-frontend-foundation.md](tasks/003-frontend-foundation.md)

**What gets built:**
- Next.js app with App Router
- Layout with sidebar and header
- Auth integration (NextAuth.js + Entra ID B2C stub)
- API client wrapper
- React Query provider
- Tailwind + shadcn/ui setup
- Landing page and login flow

**Acceptance Criteria:**
- [ ] App loads in browser at `localhost:3000`
- [ ] Login flow redirects to auth provider
- [ ] Authenticated layout renders sidebar and header
- [ ] API client can make requests to the backend
- [ ] Tailwind styles render correctly

---

## Phase 4: Tenancy, Auth, and Subscription Foundation

**Task:** [004-tenancy-auth-and-subscription-foundation.md](tasks/004-tenancy-auth-and-subscription-foundation.md)

**What gets built:**
- Auth middleware (JWT validation)
- Tenant context middleware
- Quota enforcement middleware
- Tenant CRUD endpoints
- User creation on first login
- Tier definitions (free tier)
- Quota check service
- Cosmos DB `tenants` container setup

**Acceptance Criteria:**
- [ ] JWT validation rejects invalid tokens
- [ ] Tenant context is available in route handlers
- [ ] Quota middleware returns 429 when limits exceeded
- [ ] `POST /api/v1/tenants` creates a tenant
- [ ] `GET /api/v1/tenants/me` returns the current tenant with usage
- [ ] Free tier limits are enforced

---

## Phase 5: Project and Artifact Domain

**Task:** [005-project-and-artifact-domain.md](tasks/005-project-and-artifact-domain.md)

**What gets built:**
- Project CRUD endpoints
- Artifact metadata endpoints (no upload yet)
- Artifact state machine
- Cosmos DB `projects` container setup
- Project listing with pagination

**Acceptance Criteria:**
- [ ] `POST /api/v1/projects` creates a project (quota enforced)
- [ ] `GET /api/v1/projects` lists projects for tenant
- [ ] `GET /api/v1/projects/{id}` returns project details
- [ ] Artifact status enum and state transitions are defined
- [ ] Project soft-delete works

---

## Phase 6: Upload Flow and Storage

**Task:** [006-upload-flow-and-storage.md](tasks/006-upload-flow-and-storage.md)

**What gets built:**
- Multipart artifact upload endpoint
- Blob Storage upload
- Artifact type detection
- Content hash computation
- ArtifactUploaded event publishing
- Artifact download endpoint
- Frontend upload UI

**Acceptance Criteria:**
- [ ] Upload a Logic App JSON file → stored in Blob → metadata in Cosmos
- [ ] Artifact type is detected correctly
- [ ] ArtifactUploaded event is published to Event Grid
- [ ] Quota limits are enforced (file size, artifact count)
- [ ] Frontend shows upload progress and status

---

## Phase 7: Eventing Foundation

**Task:** [007-eventing-foundation.md](tasks/007-eventing-foundation.md)

**What gets built:**
- Event Grid Namespace publisher (shared library)
- Event Grid pull delivery consumer (shared library)
- CloudEvents envelope builder
- Worker base class with pull loop, idempotency, error handling
- Scan-gate worker (passthrough for MVP)
- Dead-letter handling

**Acceptance Criteria:**
- [ ] Events can be published to Event Grid Namespace
- [ ] Workers can pull events from subscriptions
- [ ] CloudEvents envelope is correctly formatted
- [ ] Scan-gate worker transitions artifact status to `scan_passed`
- [ ] Dead-letter path works for failed events

---

## Phase 8: Parser Worker

**Task:** [008-parser-worker.md](tasks/008-parser-worker.md)

**What gets built:**
- Parser worker Container App entry point
- Logic App workflow parser
- OpenAPI spec parser
- APIM policy XML parser
- Parse result storage in Cosmos DB
- ArtifactParsed / ArtifactParseFailed event publishing

**Acceptance Criteria:**
- [ ] Logic App JSON is parsed into components and edges
- [ ] OpenAPI spec is parsed into API definitions and operations
- [ ] APIM policy XML is parsed into policy components
- [ ] Parse results are stored in Cosmos DB
- [ ] Artifact status transitions correctly
- [ ] Parse failures are handled gracefully

---

## Phase 9: Graph Builder and Persistence

**Task:** [009-graph-builder-and-persistence.md](tasks/009-graph-builder-and-persistence.md)

**What gets built:**
- Graph builder worker
- Component upsert logic (deterministic IDs)
- Edge upsert logic
- Graph summary computation
- Cosmos DB `graph` container setup
- Graph query API endpoints
- Frontend graph visualization

**Acceptance Criteria:**
- [ ] Parse results are transformed into graph components and edges
- [ ] Component IDs are deterministic (re-upload = update, not duplicate)
- [ ] Graph summary is computed and stored
- [ ] `GET /api/v1/projects/{id}/graph/summary` returns summary
- [ ] `GET /api/v1/projects/{id}/graph/components` returns components
- [ ] Frontend renders a graph visualization

---

## Phase 10: Foundry Agent, Tools, and Analysis Flow

**Task:** [010-foundry-agent-tools-and-analysis-flow.md](tasks/010-foundry-agent-tools-and-analysis-flow.md)

**What gets built:**
- AI Foundry infrastructure via Bicep (AI Services account, project, GPT-4o model deployment at 30K TPM, RBAC)
- Analysis API endpoints
- Analysis worker using Microsoft Agent Framework SDK
- Two agents: integration-analyst (with four FunctionTool definitions) and quality-evaluator (validates analyst responses)
- Four custom tools (get_project_summary, get_graph_neighbors, get_component_details, run_impact_analysis) as typed Python functions
- Tenant/project scoping enforcement in tools
- Analyst → evaluator flow with up to 1 retry on failed evaluation
- Analysis result storage with evaluation metadata
- Notification worker + Web PubSub integration
- Frontend analysis chat UI

**Acceptance Criteria:**
- [ ] AI Services account provisioned via Bicep with `kind: AIServices`
- [ ] GPT-4o model deployed with GlobalStandard SKU at 30K TPM
- [ ] Worker managed identity has `Cognitive Services User` on the AI Services account
- [ ] `POST /api/v1/projects/{id}/analyses` creates an analysis request
- [ ] Microsoft Agent Framework SDK is used for agent orchestration
- [ ] Integration-analyst agent calls custom tools that query the real graph
- [ ] Quality-evaluator agent validates analyst responses against tool evidence
- [ ] Failed evaluations trigger one analyst retry
- [ ] Analysis results include evaluation metadata (verdict, confidence, issues)
- [ ] Tools enforce tenant/project scoping
- [ ] Analysis results are stored in Cosmos DB
- [ ] Frontend shows analysis chat with results
- [ ] Web PubSub notifications work end-to-end

---

## Anti-Goals (Prevent Overengineering)

| Do Not | Why |
|--------|-----|
| Build a generic plugin system | MVP has a fixed set of parsers and tools |
| Implement CQRS or event sourcing | Overkill for MVP data volumes |
| Build a custom graph database | Cosmos DB document model is sufficient |
| Add multi-region support | Single region for MVP |
| Build a custom WebSocket server | Web PubSub is managed |
| Add paid tier logic | Design for it, don't build it |
| Add CI/CD deployment automation beyond skeleton | Operational concern, not MVP feature |
| Build an admin portal | API + Cosmos DB explorer is sufficient for MVP ops |
| Implement custom rate limiting | Tier-based quota checks are sufficient |
| Add OpenAPI client generation | Manual TypeScript types are fine for MVP |

---

## How to Execute This Plan with an AI Coding Agent

### Execution Model

1. **Give the agent one task packet at a time.** Each task in `/docs/plan/tasks/` is self-contained and designed for a single focused work cycle.
2. **Tasks are numbered in execution order.** Follow the numbering unless explicitly parallelizing (e.g., tasks 002 and 003 can run concurrently).
3. **Each task includes acceptance criteria.** The agent should verify all criteria before marking the task complete.
4. **Reference the domain docs for context.** Each task references the relevant domain documents (01–09). The agent should read those for detailed data models, event schemas, and API contracts.

### Agent Instructions Template

```
Read the following task packet: /docs/plan/tasks/NNN-task-name.md

Context documents (read as needed):
- /docs/plan/01-system-architecture.md
- /docs/plan/0X-relevant-domain-doc.md

Execute the task:
1. Read the task packet fully.
2. Create/modify the files listed in "Files/directories expected to be created or modified."
3. Follow the "Implementation notes" section.
4. Verify all items in "Acceptance criteria."
5. Run all items in "Suggested validation steps."
6. Report completion.
```

### Parallelization Opportunities

| Parallel Pair | Condition |
|--------------|-----------|
| Task 002 + Task 003 | Both depend only on Task 001 |
| Task 005 + Task 007 | Both depend on Task 002/004 but are independent |

### Checkpoints

After each task, verify:
- [ ] All acceptance criteria pass
- [ ] No regressions in previous tasks (run full test suite)
- [ ] Linting passes
- [ ] Docker compose still works

---

## Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| Task granularity | 10 tasks for MVP | Each task is ~1 focused work cycle |
| Execution order | Linear with parallelization opportunities | Minimizes rework; each task builds on prior |
| Testing strategy | Per-task acceptance criteria + validation steps | Practical, incremental verification |
