# 04 — Domain: Graph and Metadata

## Goals

- Define graph concepts: components, edges, graph versions, and summaries.
- Define how parsing output becomes normalized graph data.
- Define the Cosmos DB container strategy and document shapes.
- Define what metadata is queryable versus what remains in raw artifacts.
- Define graph versioning for MVP.

## Scope

MVP: single-project graphs, deterministic parsing to graph, Cosmos DB storage, version tracking.

Future: cross-project graphs, graph diff, temporal graph queries.

---

## Graph Concepts

### Component

A **component** is a discrete unit discovered during artifact parsing. It represents a "thing" in the integration landscape.

Examples:
- A Logic App workflow
- An HTTP action within a workflow
- An API operation defined in an OpenAPI spec
- An APIM policy applied to an operation
- A backend service referenced by a policy

### Edge

An **edge** is a directed relationship between two components.

Examples:
- Logic App workflow → calls → HTTP endpoint
- API operation → has policy → rate-limit policy
- Logic App action → references → Service Bus queue

### Graph Version

Each time the graph for a project is updated (artifact parsed + graph built), the graph version increments. This is a simple integer counter on the project document.

### Graph Summary

A pre-computed summary of the graph for a project, used by the agent and the UI dashboard.

---

## Component Entity

```json
{
  "id": "cmp_01HQ...",
  "partitionKey": "tn_01HQXYZ...:prj_01HQ...",
  "type": "component",
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "artifactId": "art_01HQ...",
  "componentType": "logic_app_workflow",
  "name": "order-processor",
  "displayName": "Order Processor Workflow",
  "properties": {
    "triggerType": "http",
    "actionCount": 15,
    "hasRetryPolicy": true
  },
  "tags": ["order-processing", "http-triggered"],
  "graphVersion": 3,
  "createdAt": "2026-03-25T14:32:00Z",
  "updatedAt": "2026-03-25T14:32:00Z"
}
```

### Component Types

| Type | Source Artifact | Description |
|------|----------------|-------------|
| `logic_app_workflow` | Logic App JSON | A complete workflow definition |
| `logic_app_action` | Logic App JSON | An action within a workflow (HTTP, Service Bus, etc.) |
| `logic_app_trigger` | Logic App JSON | A trigger within a workflow |
| `api_definition` | OpenAPI spec | An API defined by an OpenAPI spec |
| `api_operation` | OpenAPI spec | A single operation (GET /orders, POST /items, etc.) |
| `api_schema` | OpenAPI spec | A request/response schema |
| `apim_policy` | APIM policy XML | A policy applied at API, operation, or global level |
| `apim_policy_fragment` | APIM policy XML | A reusable policy fragment |
| `external_service` | Any (inferred) | A service referenced but not defined in uploaded artifacts |

---

## Edge Entity

```json
{
  "id": "edg_01HQ...",
  "partitionKey": "tn_01HQXYZ...:prj_01HQ...",
  "type": "edge",
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "sourceComponentId": "cmp_01HQAAA...",
  "targetComponentId": "cmp_01HQBBB...",
  "edgeType": "calls",
  "properties": {
    "method": "POST",
    "path": "/api/orders"
  },
  "artifactId": "art_01HQ...",
  "graphVersion": 3,
  "createdAt": "2026-03-25T14:32:00Z"
}
```

### Edge Types

| Type | Description | Example |
|------|-------------|---------|
| `calls` | Source invokes target | Workflow → HTTP endpoint |
| `triggers` | Source triggers target | Timer → Workflow |
| `has_operation` | API contains operation | API definition → GET /orders |
| `has_policy` | Operation/API has policy | API operation → rate-limit policy |
| `references` | Source references target | Action → Service Bus queue |
| `produces` | Source produces to target | Workflow → Event Grid topic |
| `consumes` | Source consumes from target | Workflow → Service Bus subscription |
| `depends_on` | Generic dependency | Component → external service |

---

## Parsing Output → Graph Data

### Parsing Pipeline

```
Raw artifact (blob)
  ↓
Type-specific parser
  ↓
ParseResult {
  components: Component[],
  edges: Edge[],
  metadata: { ... }
}
  ↓
Stored as parse_result document in Cosmos DB
  ↓
Graph builder reads parse_result
  ↓
Upserts components and edges into graph containers
```

### Parse Result Entity

```json
{
  "id": "pr_01HQ...",
  "partitionKey": "tn_01HQXYZ...",
  "type": "parse_result",
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "artifactId": "art_01HQ...",
  "artifactType": "logic_app_workflow",
  "components": [
    {
      "tempId": "temp_wf_1",
      "componentType": "logic_app_workflow",
      "name": "order-processor",
      "displayName": "Order Processor Workflow",
      "properties": { "triggerType": "http", "actionCount": 15 }
    },
    {
      "tempId": "temp_act_1",
      "componentType": "logic_app_action",
      "name": "HTTP_Call_OrderAPI",
      "displayName": "Call Order API",
      "properties": { "actionType": "Http", "method": "POST", "uri": "https://api.contoso.com/orders" }
    }
  ],
  "edges": [
    {
      "sourceTempId": "temp_wf_1",
      "targetTempId": "temp_act_1",
      "edgeType": "calls"
    }
  ],
  "externalReferences": [
    {
      "tempId": "temp_ext_1",
      "componentType": "external_service",
      "name": "api.contoso.com",
      "displayName": "Contoso Order API (external)",
      "inferredFrom": "HTTP action URI"
    }
  ],
  "parsedAt": "2026-03-25T14:32:00Z"
}
```

### Graph Builder Logic

1. For each component in the parse result:
   - Generate a stable component ID (based on `tenantId + projectId + componentType + name`).
   - Upsert into the `graph` container (insert or replace).
2. For each edge in the parse result:
   - Resolve `sourceTempId` and `targetTempId` to stable component IDs.
   - Generate a stable edge ID (based on `sourceId + targetId + edgeType`).
   - Upsert into the `graph` container.
3. For each external reference:
   - Create/upsert an `external_service` component.
   - Create an edge from the referencing component to the external service.
4. Increment the project's `graphVersion`.
5. Update or create the graph summary document.

### Component ID Stability

Component IDs must be deterministic so that re-uploading the same artifact updates existing graph nodes rather than creating duplicates.

```
component_id = hash(tenantId + projectId + componentType + canonicalName)
```

The `canonicalName` is the normalized name extracted by the parser (e.g., workflow name, operation ID, policy name).

---

## Graph Summary Entity

```json
{
  "id": "gs_01HQ...",
  "partitionKey": "tn_01HQXYZ...:prj_01HQ...",
  "type": "graph_summary",
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "graphVersion": 3,
  "totalComponents": 42,
  "totalEdges": 67,
  "componentCounts": {
    "logic_app_workflow": 3,
    "logic_app_action": 22,
    "api_definition": 2,
    "api_operation": 8,
    "apim_policy": 4,
    "external_service": 3
  },
  "edgeCounts": {
    "calls": 15,
    "has_operation": 8,
    "has_policy": 4,
    "references": 12,
    "depends_on": 3
  },
  "updatedAt": "2026-03-25T14:35:00Z"
}
```

---

## Cosmos DB Container Strategy

### Containers

| Container | Partition Key | Document Types | Purpose |
|-----------|--------------|----------------|---------|
| `tenants` | `/partitionKey` = `{tenantId}` | `tenant`, `user`, `tier_definition` | Tenancy data |
| `projects` | `/partitionKey` = `{tenantId}` | `project`, `artifact`, `parse_result` | Project and artifact data |
| `graph` | `/partitionKey` = `{tenantId}:{projectId}` | `component`, `edge`, `graph_summary` | Graph data |
| `analyses` | `/partitionKey` = `{tenantId}` | `analysis` | Analysis requests and results |

### Why These Partition Keys

- **`tenants`**: All tenant data is co-located. User lookups are within the tenant partition.
- **`projects`**: All project/artifact data for a tenant is co-located. Listing projects and their artifacts is a single-partition query.
- **`graph`**: Partitioned by `tenantId:projectId` because graph queries are always project-scoped. This keeps all graph data for a project together for efficient traversal.
- **`analyses`**: Partitioned by tenant because analysis listing and daily quota checks are tenant-scoped.

### Indexing

- Use default Cosmos DB indexing for MVP (all paths indexed).
- Add composite indexes if query performance requires it post-MVP.

---

## Queryable Metadata vs. Raw Artifacts

| Data | Stored In | Queryable | Purpose |
|------|-----------|-----------|---------|
| Component name, type, properties | Cosmos DB (`graph` container) | ✅ Yes | Graph queries, agent tools |
| Edge source, target, type | Cosmos DB (`graph` container) | ✅ Yes | Graph traversal, impact analysis |
| Artifact metadata (name, type, status) | Cosmos DB (`projects` container) | ✅ Yes | API listing, status tracking |
| Parse result (components + edges) | Cosmos DB (`projects` container) | ✅ Yes | Re-building graph, debugging |
| Graph summary | Cosmos DB (`graph` container) | ✅ Yes | Dashboard, agent context |
| Raw artifact file content | Blob Storage | ❌ No (fetch by path) | Download, re-parse |
| Inline code/XML from raw artifacts | Not extracted separately | ❌ No | Remains in blob |

The principle: **extract structure into the graph, keep raw content in blobs.** The agent and UI operate on the graph, not on raw files.

---

## Graph Versioning (MVP)

- Each project has a `graphVersion` integer.
- Every successful graph build increments the version.
- Components and edges are tagged with the `graphVersion` they were created/updated in.
- MVP does not support querying historical graph versions.
- MVP does not support graph diffing between versions.

### Future: Graph Versioning

- Store point-in-time snapshots of the graph summary.
- Support "what changed in version N" queries.
- Support graph diff between two versions.

---

## Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| Graph partition key | `{tenantId}:{projectId}` | All graph data for a project is co-located; efficient for traversal |
| Component ID generation | Deterministic hash | Idempotent upserts; re-upload updates, not duplicates |
| Parse result storage | Cosmos DB (same account) | Queryable, co-located with artifacts, useful for debugging |
| External services | Inferred components | Parsers create `external_service` nodes for referenced but undefined endpoints |
| Graph versioning | Simple counter per project | Minimal complexity for MVP; no historical queries needed |

## Assumptions

- Graph traversal depth is bounded (agent tools limit hop count).
- A single project's graph fits comfortably in a single Cosmos DB logical partition (< 20 GB for MVP).
- Parse results are small enough to store as single Cosmos DB documents (< 2 MB).

## Open Questions

| # | Question |
|---|----------|
| 1 | Should external services be de-duplicated across artifacts within a project? (Proposed: yes, by canonical URL/name) |
| 2 | Should components store a reference back to the line numbers in the raw artifact? (Proposed: not for MVP) |
