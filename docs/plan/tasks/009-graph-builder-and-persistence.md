# Task 009 — Graph Builder and Persistence

## Title

Implement the graph builder worker, Cosmos DB graph container, graph query API endpoints, and frontend graph visualization.

## Objective

Build the graph builder worker that transforms parse results into normalized graph data (components and edges) in Cosmos DB, implement the graph query API endpoints, and create the frontend graph visualization. After this task, users can see their integration landscape as a visual dependency graph.

## Why This Task Exists

The dependency graph is the core value proposition. Parsing produces structured data, but the graph builder normalizes it into a queryable, visualizable graph. The graph query endpoints power both the frontend visualization and the agent tools (task 010).

## In Scope

- Graph builder worker using the worker base class
- Cosmos DB `graph` container creation (components, edges, graph summary)
- Component upsert with deterministic ID generation
- Edge upsert with deterministic ID generation
- Graph summary computation and storage
- Graph version incrementing on the project document
- Graph query API endpoints:
  - `GET /api/v1/projects/{id}/graph/summary`
  - `GET /api/v1/projects/{id}/graph/components` (paginated)
  - `GET /api/v1/projects/{id}/graph/components/{componentId}`
  - `GET /api/v1/projects/{id}/graph/components/{componentId}/neighbors`
  - `GET /api/v1/projects/{id}/graph/edges` (paginated)
- `GraphUpdated` / `GraphBuildFailed` event publishing
- Artifact status transitions: `parsed` → `graph_building` → `graph_built`
- Frontend: graph visualization page, component detail panel, graph summary

## Out of Scope

- Agent tools that query the graph (task 010)
- Cross-project graph queries
- Graph diff or versioning history
- Graph export

## Dependencies

- **Task 008** (parser worker): Parse results in Cosmos DB.
- **Task 007** (eventing foundation): Worker base class, event consumer/publisher.
- **Task 005** (project/artifact domain): Project and artifact repositories.

## Files/Directories Expected to Be Created or Modified

```
src/backend/
├── workers/
│   └── graph_builder/
│       ├── __init__.py
│       ├── main.py                # Entry point for graph builder worker
│       └── handler.py             # Graph builder event handler
├── domains/
│   └── graph/
│       ├── __init__.py
│       ├── router.py              # Graph query routes
│       ├── service.py             # GraphService
│       ├── models.py              # Component, Edge, GraphSummary Pydantic models
│       └── repository.py          # Cosmos DB operations for graph container
├── main.py                        # Updated: register graph router
src/frontend/
├── src/
│   ├── app/(dashboard)/projects/[projectId]/graph/
│   │   └── page.tsx               # Graph visualization page
│   ├── components/graph/
│   │   ├── graph-canvas.tsx        # Graph rendering component
│   │   ├── component-panel.tsx     # Component detail sidebar
│   │   └── graph-summary.tsx       # Summary statistics card
│   └── hooks/
│       └── use-graph.ts            # React Query hooks for graph
tests/backend/
├── test_graph_builder.py
├── test_graph_api.py
└── test_component_id_generation.py
```

## Implementation Notes

### Deterministic Component ID Generation

```python
import hashlib

def generate_component_id(tenant_id: str, project_id: str, component_type: str, canonical_name: str) -> str:
    """Generate a deterministic component ID from its defining attributes."""
    key = f"{tenant_id}:{project_id}:{component_type}:{canonical_name}"
    hash_hex = hashlib.sha256(key.encode()).hexdigest()[:20]
    return f"cmp_{hash_hex}"

def generate_edge_id(source_id: str, target_id: str, edge_type: str) -> str:
    """Generate a deterministic edge ID from its endpoints and type."""
    key = f"{source_id}:{target_id}:{edge_type}"
    hash_hex = hashlib.sha256(key.encode()).hexdigest()[:20]
    return f"edg_{hash_hex}"
```

This ensures:
- Re-uploading the same artifact updates existing graph nodes, not duplicates.
- The same component always gets the same ID regardless of when it was parsed.

### Graph Builder Handler

```python
class GraphBuilderHandler:
    async def handle(self, event_data: dict):
        tenant_id = event_data["tenantId"]
        project_id = event_data["projectId"]
        artifact_id = event_data["artifactId"]
        parse_result_id = event_data["parseResultId"]

        # Transition artifact status
        await self.artifact_repo.update_status(tenant_id, artifact_id, "graph_building")

        # Load parse result
        parse_result = await self.parse_result_repo.get(tenant_id, parse_result_id)

        # Build temp_id → stable_id mapping
        id_map = {}
        
        # 1. Upsert components
        for comp in parse_result["components"]:
            stable_id = generate_component_id(tenant_id, project_id, comp["componentType"], comp["name"])
            id_map[comp["tempId"]] = stable_id
            
            component_doc = {
                "id": stable_id,
                "partitionKey": f"{tenant_id}:{project_id}",
                "type": "component",
                "tenantId": tenant_id,
                "projectId": project_id,
                "artifactId": artifact_id,
                "componentType": comp["componentType"],
                "name": comp["name"],
                "displayName": comp["displayName"],
                "properties": comp.get("properties", {}),
                "graphVersion": current_version + 1,
                "updatedAt": now_iso,
            }
            await self.graph_repo.upsert_component(component_doc)

        # 2. Upsert external references
        for ext in parse_result.get("externalReferences", []):
            stable_id = generate_component_id(tenant_id, project_id, "external_service", ext["name"])
            id_map[ext["tempId"]] = stable_id
            await self.graph_repo.upsert_component({...})

        # 3. Upsert edges
        for edge in parse_result["edges"]:
            source_id = id_map[edge["sourceTempId"]]
            target_id = id_map[edge["targetTempId"]]
            edge_id = generate_edge_id(source_id, target_id, edge["edgeType"])
            
            edge_doc = {
                "id": edge_id,
                "partitionKey": f"{tenant_id}:{project_id}",
                "type": "edge",
                "tenantId": tenant_id,
                "projectId": project_id,
                "sourceComponentId": source_id,
                "targetComponentId": target_id,
                "edgeType": edge["edgeType"],
                "properties": edge.get("properties"),
                "artifactId": artifact_id,
                "graphVersion": current_version + 1,
            }
            await self.graph_repo.upsert_edge(edge_doc)

        # 4. Update graph summary
        summary = await self._compute_summary(tenant_id, project_id, current_version + 1)
        await self.graph_repo.upsert_summary(summary)

        # 5. Increment project graph version
        await self.project_repo.increment_graph_version(tenant_id, project_id)

        # 6. Update artifact status
        await self.artifact_repo.update_status(tenant_id, artifact_id, "graph_built")

        # 7. Publish GraphUpdated event
        await self.event_publisher.publish(...)
```

### Graph Summary Computation

```python
async def _compute_summary(self, tenant_id: str, project_id: str, version: int) -> dict:
    partition_key = f"{tenant_id}:{project_id}"
    
    # Count components by type
    component_counts = await self.graph_repo.count_by_type(partition_key, "component")
    
    # Count edges by type
    edge_counts = await self.graph_repo.count_by_type(partition_key, "edge")
    
    return {
        "id": f"gs_{generate_hash(tenant_id, project_id)}",
        "partitionKey": partition_key,
        "type": "graph_summary",
        "tenantId": tenant_id,
        "projectId": project_id,
        "graphVersion": version,
        "totalComponents": sum(component_counts.values()),
        "totalEdges": sum(edge_counts.values()),
        "componentCounts": component_counts,
        "edgeCounts": edge_counts,
        "updatedAt": now_iso,
    }
```

### Graph Query API

```python
# domains/graph/router.py
@router.get("/api/v1/projects/{project_id}/graph/summary")
async def get_graph_summary(project_id: str, request: Request):
    tenant = request.state.tenant
    summary = await graph_service.get_summary(tenant.id, project_id)
    return ResponseEnvelope(data=summary, meta=build_meta(request))

@router.get("/api/v1/projects/{project_id}/graph/components")
async def list_components(project_id: str, request: Request, page: int = 1, page_size: int = 20, component_type: str | None = None):
    tenant = request.state.tenant
    components, total = await graph_service.list_components(tenant.id, project_id, page, page_size, component_type)
    return PaginatedResponse(data=components, meta=build_meta(request), pagination=build_pagination(page, page_size, total))

@router.get("/api/v1/projects/{project_id}/graph/components/{component_id}/neighbors")
async def get_neighbors(project_id: str, component_id: str, request: Request, direction: str = "both"):
    tenant = request.state.tenant
    neighbors = await graph_service.get_neighbors(tenant.id, project_id, component_id, direction)
    return ResponseEnvelope(data=neighbors, meta=build_meta(request))
```

### Frontend Graph Visualization

Use a graph rendering library (e.g., `react-flow` or `cytoscape.js`) to display:
- Nodes: components, colored by type
- Edges: directed arrows between nodes
- Click node: opens a component detail panel
- Filter: by component type
- Summary card: total components, edges, version

The graph page fetches data from the API and renders client-side. Use React Query for data fetching with automatic cache invalidation on `GraphUpdated` notifications.

## Acceptance Criteria

- [ ] Graph builder worker consumes `ArtifactParsed` events
- [ ] Parse results are transformed into component and edge documents in Cosmos DB
- [ ] Component IDs are deterministic (same input → same ID)
- [ ] Re-uploading the same artifact updates existing components, not duplicates
- [ ] Graph summary is computed and stored
- [ ] Project `graphVersion` is incremented
- [ ] Artifact status transitions: `parsed` → `graph_building` → `graph_built`
- [ ] `GraphUpdated` event is published
- [ ] `GET /graph/summary` returns graph summary
- [ ] `GET /graph/components` returns paginated components
- [ ] `GET /graph/components/{id}` returns component details
- [ ] `GET /graph/components/{id}/neighbors` returns connected components
- [ ] Frontend renders graph visualization with nodes and edges
- [ ] Frontend component detail panel shows properties
- [ ] All queries are tenant/project-scoped

## Definition of Done

- The full pipeline works: upload → scan → parse → graph build.
- Graph data is queryable via API.
- Frontend shows the graph visualization.
- The agent tools task (010) can query graph data through the GraphService.

## Risks / Gotchas

- **Cosmos DB write throughput**: Many upserts in sequence. Consider batching operations if performance is an issue.
- **Partition key format**: Graph container uses composite key `{tenantId}:{projectId}`. Ensure all queries include it.
- **Graph rendering performance**: Large graphs may be slow to render client-side. Paginate and virtualize for MVP.
- **Deterministic IDs and renaming**: If a component is renamed in the artifact, it gets a new ID (different canonical name). The old component remains as a stale entry. Consider a garbage collection strategy for future.

## Suggested Validation Steps

1. Upload a Logic App workflow → verify scan → parse → graph build pipeline completes.
2. Check Cosmos DB `graph` container: verify component and edge documents.
3. Call `GET /graph/summary` → verify counts match parse result.
4. Call `GET /graph/components` → verify components are returned with correct types.
5. Call `GET /graph/components/{id}/neighbors` → verify edges are resolved.
6. Re-upload the same artifact → verify component IDs are the same (no duplicates).
7. Upload a second artifact → verify graph version increments and summary updates.
8. Open the frontend graph page → verify visualization renders.
9. Click a node → verify component detail panel opens.
