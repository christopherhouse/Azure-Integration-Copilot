# 06 — Domain: Agents and Tools

## Goals

- Define the MVP agent strategy using Azure AI Foundry Agent Service.
- Define the initial agent and its capabilities.
- Define real custom tools with input/output contracts.
- Define what the agent can do versus what must remain deterministic.
- Define tenant/project scoping rules for tool invocations.
- Define sample prompts and use cases.
- Define the analysis flow from user request to stored result.

## Scope

MVP: one agent, four custom tools, project-scoped analysis, results stored in Cosmos DB.

Future: multiple specialized agents, agent-to-agent orchestration, custom user prompts.

---

## Agent Strategy

### Principles

1. **Real tools only.** No simulated or mocked agent behavior. Every tool call hits real data.
2. **Deterministic parsing first, agent reasoning second.** The graph is built by deterministic parsers. The agent reasons over the structured graph, not raw artifact files.
3. **Single agent for MVP.** One agent handles all analysis use cases. Agent routing/specialization is future scope.
4. **Tenant/project scoping is non-negotiable.** Every tool call is scoped to a specific tenant and project. The agent cannot access cross-tenant data.

### Why Foundry Agent Service

| Concern | Custom LLM Integration | Foundry Agent Service (chosen) |
|---------|----------------------|-------------------------------|
| Tool calling | Must implement tool dispatch | Built-in tool calling with function definitions |
| Conversation management | Must build conversation state | Managed by the service |
| Hosting | Self-hosted inference | Managed service |
| Iteration speed | High (custom code for every feature) | Medium (define tools, let service handle orchestration) |

---

## Initial Agent

### Agent Definition

| Property | Value |
|----------|-------|
| Agent Name | `integration-analyst` |
| Model | GPT-4o (or latest available in Foundry) |
| Temperature | 0.3 (prefer precision over creativity) |
| Max tokens | 4096 |
| Tools | `get_project_summary`, `get_graph_neighbors`, `get_component_details`, `run_impact_analysis` |

### System Prompt

```
You are an integration analyst for the Integration Copilot platform.

You help users understand their Azure integration landscape by analyzing the dependency graph built from their uploaded artifacts.

You have access to tools that query the project's dependency graph. Use these tools to answer the user's questions.

Rules:
- Always use the tools to look up data. Do not guess or fabricate component names, connections, or counts.
- If the graph does not contain enough information to answer, say so clearly.
- When describing impact or dependencies, cite specific component names and edge types.
- Keep answers concise and actionable.
- Do not discuss implementation details of the platform itself.

Context:
- Tenant: {tenantId}
- Project: {projectId}
- Graph version: {graphVersion}
- Components: {totalComponents}
- Edges: {totalEdges}
```

---

## Custom Tools

### Tool 1: `get_project_summary`

Returns the graph summary for the current project.

**Input:**
```json
{
  "tenantId": "string (injected, not user-provided)",
  "projectId": "string (injected, not user-provided)"
}
```

**Output:**
```json
{
  "projectName": "Order Processing Integration",
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
  }
}
```

**Implementation:** Query the `graph_summary` document from Cosmos DB.

---

### Tool 2: `get_graph_neighbors`

Returns the immediate neighbors (incoming and outgoing edges) for a given component.

**Input:**
```json
{
  "tenantId": "string (injected)",
  "projectId": "string (injected)",
  "componentId": "string",
  "direction": "both | incoming | outgoing",
  "maxDepth": 1
}
```

**Output:**
```json
{
  "component": {
    "id": "cmp_01HQ...",
    "name": "order-processor",
    "componentType": "logic_app_workflow"
  },
  "neighbors": [
    {
      "component": {
        "id": "cmp_01HQBBB...",
        "name": "Call Order API",
        "componentType": "logic_app_action"
      },
      "edge": {
        "edgeType": "calls",
        "direction": "outgoing"
      }
    },
    {
      "component": {
        "id": "cmp_01HQCCC...",
        "name": "HTTP Trigger",
        "componentType": "logic_app_trigger"
      },
      "edge": {
        "edgeType": "triggers",
        "direction": "incoming"
      }
    }
  ]
}
```

**Implementation:** Query `graph` container for edges where `sourceComponentId` or `targetComponentId` matches, then load the connected components.

---

### Tool 3: `get_component_details`

Returns detailed information about a specific component.

**Input:**
```json
{
  "tenantId": "string (injected)",
  "projectId": "string (injected)",
  "componentId": "string"
}
```

**Output:**
```json
{
  "id": "cmp_01HQ...",
  "componentType": "logic_app_workflow",
  "name": "order-processor",
  "displayName": "Order Processor Workflow",
  "properties": {
    "triggerType": "http",
    "actionCount": 15,
    "hasRetryPolicy": true
  },
  "tags": ["order-processing", "http-triggered"],
  "artifactId": "art_01HQ...",
  "incomingEdgeCount": 2,
  "outgoingEdgeCount": 8
}
```

**Implementation:** Read component document from `graph` container, count edges.

---

### Tool 4: `run_impact_analysis`

Performs a breadth-first traversal from a component to find all transitively dependent components.

**Input:**
```json
{
  "tenantId": "string (injected)",
  "projectId": "string (injected)",
  "componentId": "string",
  "direction": "downstream | upstream",
  "maxDepth": 3
}
```

**Output:**
```json
{
  "rootComponent": {
    "id": "cmp_01HQ...",
    "name": "Order API",
    "componentType": "api_definition"
  },
  "impactedComponents": [
    {
      "component": {
        "id": "cmp_01HQAAA...",
        "name": "order-processor",
        "componentType": "logic_app_workflow"
      },
      "depth": 1,
      "path": ["Order API", "→ calls →", "order-processor"]
    },
    {
      "component": {
        "id": "cmp_01HQBBB...",
        "name": "inventory-check",
        "componentType": "logic_app_action"
      },
      "depth": 2,
      "path": ["Order API", "→ calls →", "order-processor", "→ calls →", "inventory-check"]
    }
  ],
  "totalImpacted": 5,
  "maxDepthReached": false
}
```

**Implementation:** BFS traversal over graph edges in Cosmos DB. Limit depth to prevent runaway queries. Limit total results to 100 components.

---

## Agent Boundaries

### What the Agent Can Do

- Query the graph via tools.
- Reason about component relationships, dependencies, and impact.
- Synthesize findings into natural language answers.
- Make recommendations based on graph structure.

### What Must Remain Deterministic

- Artifact parsing (always code, never LLM).
- Graph construction (always deterministic upserts, never LLM).
- Status transitions (always state machine, never LLM).
- Quota enforcement (always policy check, never LLM).

### What the Agent Cannot Do

- Modify the graph.
- Upload or delete artifacts.
- Change project or tenant settings.
- Access data from other tenants or projects.
- Execute code or infrastructure changes.

---

## Tenant/Project Scoping Rules

1. When the API creates an analysis request, it includes `tenantId` and `projectId` in the event data.
2. The Analysis Worker reads these from the event and passes them to the agent as context.
3. All tool function definitions include `tenantId` and `projectId` as required parameters, but these are **injected by the worker**, not provided by the LLM.
4. The tool implementation includes a guard:
   ```python
   def tool_handler(params: ToolParams, context: AnalysisContext):
       # Override any tenantId/projectId from params with the context values
       tenant_id = context.tenant_id  # from event, not from LLM
       project_id = context.project_id  # from event, not from LLM
       # Query Cosmos DB with enforced scope
   ```
5. The LLM can choose which tool to call and what `componentId` or `direction` to use, but it cannot choose which tenant or project to query.

---

## Sample Prompts and Use Cases

| Use Case | Sample Prompt | Expected Tool Usage |
|----------|--------------|-------------------|
| Overview | "Summarize this project's integration landscape" | `get_project_summary` |
| Dependency lookup | "What does the order-processor workflow call?" | `get_graph_neighbors` (outgoing) |
| Reverse dependency | "What calls the Order API?" | `get_graph_neighbors` (incoming) |
| Component deep-dive | "Tell me about the rate-limit policy" | `get_component_details` |
| Impact analysis | "What breaks if the Order API goes down?" | `run_impact_analysis` (downstream) |
| Change planning | "I'm going to change the inventory-check action. What's affected?" | `run_impact_analysis` (downstream) + `get_component_details` |
| Architecture review | "Are there any components with no incoming connections?" | `get_project_summary` + multiple `get_graph_neighbors` calls |

---

## Analysis Flow

### End-to-End

```
1. User enters prompt in the frontend analysis UI.
2. Frontend → API POST /api/v1/projects/{id}/analyses
   - Body: { "prompt": "What breaks if the Order API goes down?" }
3. API:
   a. Validate auth + tenant context
   b. Check daily analysis quota
   c. Create analysis document (status: "pending")
   d. Publish AnalysisRequested event
   e. Return 202 with analysis ID
4. Analysis Worker pulls AnalysisRequested event.
5. Worker loads project context (graph summary, component list).
6. Worker invokes Foundry Agent Service:
   - System prompt with tenant/project context
   - User prompt from the analysis request
   - Tool definitions for all four tools
7. Agent reasons and calls tools as needed.
8. Worker intercepts tool calls, injects tenant/project scope, executes against Cosmos DB.
9. Agent produces final response.
10. Worker stores analysis result in Cosmos DB (status: "completed").
11. Worker publishes AnalysisCompleted event.
12. Notification Worker sends realtime update via Web PubSub.
13. Frontend receives notification, fetches analysis result from API.
14. Frontend displays result to user.
```

### Analysis Entity

```json
{
  "id": "anl_01HQ...",
  "partitionKey": "tn_01HQXYZ...",
  "type": "analysis",
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "prompt": "What breaks if the Order API goes down?",
  "status": "completed",
  "result": {
    "response": "The Order API is a critical dependency...",
    "toolCalls": [
      { "tool": "get_project_summary", "durationMs": 120 },
      { "tool": "run_impact_analysis", "input": { "componentId": "cmp_01HQ...", "direction": "downstream" }, "durationMs": 340 }
    ],
    "totalDurationMs": 2100,
    "modelTokensUsed": 1850
  },
  "requestedBy": "usr_01HQABC...",
  "createdAt": "2026-03-25T15:00:00Z",
  "completedAt": "2026-03-25T15:00:03Z"
}
```

### Analysis Status

| Status | Description |
|--------|-------------|
| `pending` | Created, waiting for worker |
| `in_progress` | Worker is processing |
| `completed` | Result available |
| `failed` | Agent or tool error |

---

## Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| Agent count (MVP) | 1 | Single agent with four tools covers all MVP use cases |
| Tool scoping | Tenant/project injected by worker, not LLM | Security: LLM cannot choose to access other tenants |
| Agent model | GPT-4o via Foundry | Best reasoning capability available |
| Analysis storage | Cosmos DB alongside other data | Consistent query patterns; tenant-scoped |
| Traversal depth limit | 3 hops default, max 5 | Prevents runaway graph queries |

## Assumptions

- Foundry Agent Service supports custom function/tool definitions callable from Python SDK.
- Tool call latency to Cosmos DB is < 500ms per call.
- The agent typically makes 2–5 tool calls per analysis.

## Open Questions

| # | Question |
|---|----------|
| 1 | Should analysis results include the raw tool call inputs/outputs for debugging? (Proposed: yes, in a `toolCalls` array) |
| 2 | Should the agent have access to a `search_components` tool for fuzzy name matching? (Proposed: add in a future iteration) |
