# 06 — Domain: Agents and Tools

## Goals

- Define the MVP agent strategy using Microsoft Agent Framework on Azure AI Foundry.
- Define the initial agents (analyst and quality evaluator) and their capabilities.
- Define real custom tools with input/output contracts.
- Define what agents can do versus what must remain deterministic.
- Define tenant/project scoping rules for tool invocations.
- Define the quality evaluation agent and its role in the analysis pipeline.
- Define sample prompts and use cases.
- Define the analysis flow from user request to stored result.

## Scope

MVP: two agents (integration-analyst + quality-evaluator), four custom tools, project-scoped analysis, results stored in Cosmos DB.

Future: additional specialized agents, agent-to-agent orchestration, custom user prompts.

---

## Agent Strategy

### Principles

1. **Real tools only.** No simulated or mocked agent behavior. Every tool call hits real data.
2. **Deterministic parsing first, agent reasoning second.** The graph is built by deterministic parsers. Agents reason over the structured graph, not raw artifact files.
3. **Two agents for MVP.** One analyst agent with tools, one quality evaluator agent that validates analyst responses against tool call evidence. Additional agent specialization is future scope.
4. **Tenant/project scoping is non-negotiable.** Every tool call is scoped to a specific tenant and project. Agents cannot access cross-tenant data.
5. **Validate before returning.** Every analyst response is evaluated by the quality agent before being stored. This prevents hallucinated data from reaching users.

### Why Microsoft Agent Framework

| Concern | Raw Foundry SDK (`AIProjectClient` thread/run) | Microsoft Agent Framework (chosen) |
|---------|-----------------------------------------------|------------------------------------|
| Tool calling | Manual JSON tool definitions + custom dispatch loop | `FunctionTool` auto-generates schemas from Python type hints |
| Multi-agent | Must build custom orchestration | Built-in `AgentGroupChat` with selection/termination strategies |
| Conversation management | Manual thread/run polling loop | Managed by framework via `AzureAIAgent` |
| Hosting | Managed service | Managed service (same Foundry backend) |
| Extensibility | High effort for each new pattern | Graph-based workflows, reflection, fan-out/fan-in built-in |
| Post-MVP path | Significant refactor to add agents | Add agents to existing orchestration naturally |

---

## Infrastructure Requirements

The following Azure resources must be provisioned via Bicep as part of Task 010:

| Resource | Type | Configuration |
|----------|------|---------------|
| AI Services account | `Microsoft.CognitiveServices/accounts` (kind: `AIServices`) | SKU: S0, public network access enabled (no private networking for MVP) |
| AI Foundry project | Created within the AI Services account | Links to Log Analytics for telemetry |
| GPT-4o model deployment | `Microsoft.CognitiveServices/accounts/deployments` | `GlobalStandard` SKU, 30K TPM capacity (fallback to `Standard` if quota unavailable) |
| RBAC | `Cognitive Services User` | Assigned to worker managed identity on the AI Services account |

Bicep module: `infra/bicep/modules/ai-foundry.bicep`

> **Note:** Private networking is not configured for Foundry resources in the MVP. The AI Services account uses public network access. This can be locked down post-MVP by adding private endpoints and VNet integration.

---

## Agents

### Agent 1: Integration Analyst

#### Agent Definition

| Property | Value |
|----------|-------|
| Agent Name | `integration-analyst` |
| Model | GPT-4o (deployed via Bicep) |
| Temperature | 0.3 (prefer precision over creativity) |
| Max tokens | 4096 |
| Tools | `get_project_summary`, `get_graph_neighbors`, `get_component_details`, `run_impact_analysis` |

#### System Prompt

```
You are an integration analyst for the Integrisight.ai platform.

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

### Agent 2: Quality Evaluator

#### Agent Definition

| Property | Value |
|----------|-------|
| Agent Name | `quality-evaluator` |
| Model | GPT-4o (same deployment as analyst) |
| Temperature | 0.1 (strict evaluation, minimal creativity) |
| Max tokens | 2048 |
| Tools | None (evaluates analyst output only) |

#### System Prompt

```
You are a quality evaluator for Integrisight.ai analysis responses.

You review the integration analyst's response and verify it against the tool call evidence provided.

You receive:
1. The user's original question.
2. The analyst's response.
3. The complete list of tool calls and their outputs.

Rules:
- Check that every component name, ID, count, and relationship cited in the response appears in the tool call outputs.
- Check that the response actually answers the user's question.
- If the response fabricates data not present in tool outputs, mark it as FAILED with specific citations of the fabricated claims.
- If the response is accurate but incomplete, mark it as PASSED with a note about what was missed.
- If the response is accurate and complete, mark it as PASSED.

Return a JSON object:
{
  "verdict": "PASSED" | "FAILED",
  "confidence": 0.0 to 1.0,
  "issues": ["list of specific issues found, empty if PASSED"],
  "summary": "one-sentence evaluation summary"
}
```

#### Evaluation Flow

1. Analyst produces a candidate response with tool call history.
2. Worker invokes quality-evaluator with the user prompt, analyst response, and tool call outputs.
3. Evaluator returns a structured verdict.
4. If `FAILED` and retry count < 1: the evaluator's issues are fed back to the analyst as additional context, and the analyst is asked to revise. The revised response is re-evaluated.
5. If `PASSED` or max retries reached: the final response is stored with evaluation metadata.

This adds ~1 extra LLM call per analysis (cheap with GPT-4o). Failed retries add at most 2 more calls.

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
6. Worker creates integration-analyst agent via Microsoft Agent Framework:
   - System prompt with tenant/project context
   - User prompt from the analysis request
   - FunctionTool definitions for all four tools (auto-generated from Python type hints)
7. Analyst agent reasons and calls tools as needed.
8. FunctionTool execution injects tenant/project scope, queries Cosmos DB.
9. Analyst produces candidate response.
10. Worker invokes quality-evaluator agent with: user prompt + analyst response + tool call history.
11. Evaluator returns verdict (PASSED/FAILED + issues + confidence).
12. If FAILED and retry count < 1: feed issues back to analyst for revision, re-evaluate.
13. If PASSED or max retries reached: store final result with eval metadata.
14. Worker stores analysis result in Cosmos DB (status: "completed").
15. Worker publishes AnalysisCompleted event.
16. Notification Worker sends realtime update via Web PubSub.
17. Frontend receives notification, fetches analysis result from API.
18. Frontend displays result to user.
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
    "evaluation": {
      "verdict": "PASSED",
      "confidence": 0.95,
      "issues": [],
      "summary": "Response accurately cites tool outputs and answers the user's question.",
      "retryCount": 0
    },
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
| Agent count (MVP) | 2 (analyst + quality evaluator) | Analyst answers questions; evaluator validates responses against tool evidence to prevent hallucination |
| Agent framework | Microsoft Agent Framework SDK | Built-in multi-agent support (`AgentGroupChat`), `FunctionTool` auto-schema, foundation for post-MVP patterns |
| Tool scoping | Tenant/project injected by worker, not LLM | Security: LLM cannot choose to access other tenants |
| Agent model | GPT-4o deployed via Bicep (GlobalStandard, 30K TPM) | Best reasoning capability available; single deployment shared by both agents |
| Foundry infrastructure | Bicep IaC, no private networking | AI Services account + project + model deployment provisioned automatically; private endpoints deferred to post-MVP |
| Analysis storage | Cosmos DB alongside other data | Consistent query patterns; tenant-scoped |
| Traversal depth limit | 3 hops default, max 5 | Prevents runaway graph queries |
| Eval retry policy | Max 1 retry on FAILED evaluation | Balances quality vs. cost; caps at 3 total LLM calls per analysis |

## Assumptions

- Microsoft Agent Framework SDK (`agent-framework` package) supports `FunctionTool` with auto-generated schemas from Python type hints and docstrings.
- `AIProjectClient` from `azure-ai-projects` integrates with Agent Framework for Foundry-hosted agent operations.
- Async credentials from `azure.identity.aio` are required (Agent Framework uses async patterns).
- Tool call latency to Cosmos DB is < 500ms per call.
- The analyst agent typically makes 2–5 tool calls per analysis.
- The quality evaluator adds ~1 extra LLM call per analysis (plus up to 2 more on retry).

## Open Questions

| # | Question |
|---|----------|
| 1 | Should analysis results include the raw tool call inputs/outputs for debugging? (Proposed: yes, in a `toolCalls` array) |
| 2 | Should the agent have access to a `search_components` tool for fuzzy name matching? (Proposed: add in a future iteration) |
