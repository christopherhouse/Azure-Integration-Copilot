# Prompt — Execute Task 009: Graph Builder and Persistence

You are an expert Python backend and frontend engineer. Execute the following task to implement the graph builder worker and graph visualization for Integration Copilot.

## Context

Read these documents before starting:

- **Task spec**: `docs/plan/tasks/009-graph-builder-and-persistence.md`
- **Graph and metadata domain**: `docs/plan/04-domain-graph-and-metadata.md`
- **API design**: `docs/plan/07-api-design.md`
- **Frontend UX**: `docs/plan/08-frontend-and-ux.md`

**Prerequisites**: Tasks 007 (eventing) and 008 (parser) must be complete. Parse results must be stored in Cosmos DB, and the worker base class must be operational.

## What You Must Do

Build the graph builder worker, Cosmos DB graph container, graph query API endpoints, and frontend graph visualization.

### Step 1 — Deterministic ID Generation

Create utility functions (in the graph domain or shared module):
```python
def generate_component_id(tenant_id, project_id, component_type, canonical_name) -> str:
    key = f"{tenant_id}:{project_id}:{component_type}:{canonical_name}"
    return f"cmp_{hashlib.sha256(key.encode()).hexdigest()[:20]}"

def generate_edge_id(source_id, target_id, edge_type) -> str:
    key = f"{source_id}:{target_id}:{edge_type}"
    return f"edg_{hashlib.sha256(key.encode()).hexdigest()[:20]}"
```

This ensures re-uploading the same artifact updates existing nodes, not duplicates.

### Step 2 — Graph Repository

Create `src/backend/domains/graph/repository.py`:
- Cosmos DB operations for the `graph` container (partition key: `{tenantId}:{projectId}`).
- `upsert_component(doc)`, `upsert_edge(doc)`, `upsert_summary(doc)`
- `get_summary(tenant_id, project_id)`, `list_components(tenant_id, project_id, page, page_size, component_type?)`, `get_component(tenant_id, project_id, component_id)`, `get_neighbors(tenant_id, project_id, component_id, direction)`
- `list_edges(tenant_id, project_id, page, page_size)`
- `count_by_type(partition_key, doc_type)` — for summary computation.

### Step 3 — Graph Builder Worker

Create `src/backend/workers/graph_builder/handler.py` — `GraphBuilderHandler`:
- `is_already_processed()` — True if artifact status is `graph_built` or beyond.
- `handle(event_data)`:
  1. Transition artifact to `graph_building`.
  2. Load parse result from Cosmos DB.
  3. Build `temp_id → stable_id` mapping using deterministic ID generation.
  4. Upsert components into `graph` container.
  5. Upsert external references as `external_service` components.
  6. Upsert edges, resolving temp IDs to stable IDs.
  7. Compute and upsert graph summary (total components/edges, counts by type).
  8. Increment project `graphVersion`.
  9. Update artifact status to `graph_built`.
  10. Publish `GraphUpdated` event.
- `handle_failure()` — transition to `graph_failed`.

Create `src/backend/workers/graph_builder/main.py` — entry point (subscription: `"graph-builder"`, topic: `"integration-events"`).

### Step 4 — Graph Query API

Create `src/backend/domains/graph/router.py`:
- `GET /api/v1/projects/{projectId}/graph/summary` — graph summary with component/edge counts.
- `GET /api/v1/projects/{projectId}/graph/components` — paginated component list, filterable by `component_type`.
- `GET /api/v1/projects/{projectId}/graph/components/{componentId}` — component details.
- `GET /api/v1/projects/{projectId}/graph/components/{componentId}/neighbors` — incoming/outgoing neighbors. Query param: `direction` (`both`, `incoming`, `outgoing`).
- `GET /api/v1/projects/{projectId}/graph/edges` — paginated edge list.

Create `src/backend/domains/graph/service.py` — `GraphService` wrapping repository calls.

Create `src/backend/domains/graph/models.py` — Pydantic models for `ComponentResponse`, `EdgeResponse`, `GraphSummaryResponse`, `NeighborResponse`.

Register graph router in `main.py`.

### Step 5 — Frontend Graph Visualization

Create:
- `src/frontend/src/app/(dashboard)/projects/[projectId]/graph/page.tsx` — graph visualization page.
- `src/frontend/src/components/graph/graph-canvas.tsx` — graph rendering using a library like `react-flow` or `cytoscape.js`. Nodes colored by component type, directed edges.
- `src/frontend/src/components/graph/component-panel.tsx` — sidebar showing component details when a node is clicked.
- `src/frontend/src/components/graph/graph-summary.tsx` — summary card with total components, edges, graph version.
- `src/frontend/src/hooks/use-graph.ts` — React Query hooks for graph summary, components, edges, neighbors.

Install required graph rendering library.

### Step 6 — Tests

- `tests/backend/test_component_id_generation.py` — test deterministic IDs are stable and unique.
- `tests/backend/test_graph_builder.py` — test handler end-to-end with mock parse results.
- `tests/backend/test_graph_api.py` — test graph query endpoints.

### Step 7 — Validation

1. Upload a Logic App workflow → verify scan → parse → graph build pipeline completes.
2. Check `graph` container in Cosmos DB: component and edge documents exist.
3. `GET /graph/summary` → counts match parse result.
4. `GET /graph/components` → components returned with correct types.
5. `GET /graph/components/{id}/neighbors` → edges resolved correctly.
6. Re-upload same artifact → component IDs unchanged (no duplicates).
7. Upload a second artifact → `graphVersion` increments, summary updates.
8. Frontend: graph visualization renders with nodes and edges.
9. Click a node → component detail panel opens with properties.
10. `uv run pytest tests/backend/ -v` — all tests pass.

## Constraints

- All graph queries are scoped by `{tenantId}:{projectId}` partition key.
- Component and edge IDs must be deterministic (same input = same ID).
- Graph summary is pre-computed on each build, not calculated on read.
- Do not implement agent tools for graph querying — that is task 010.
- Do not implement cross-project graph queries or graph diff.

## Done When

- Full pipeline works: upload → scan → parse → graph build.
- Graph data is queryable via API.
- Frontend renders an interactive graph visualization.
- Re-uploading artifacts updates existing graph nodes.
- All tests pass.
