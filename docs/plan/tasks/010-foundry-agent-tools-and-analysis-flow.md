# Task 010 — Foundry Agent, Tools, and Analysis Flow

## Title

Implement the AI Foundry infrastructure, Microsoft Agent Framework integration, analysis and quality-evaluation agents, custom tools, notification worker, and frontend analysis chat.

## Objective

Build the analysis flow end-to-end: provision Azure AI Foundry resources via Bicep, implement two agents (integration-analyst and quality-evaluator) using Microsoft Agent Framework SDK, build API endpoints for requesting and viewing analyses, the analysis worker that orchestrates the two-agent flow with custom tools, the notification worker that delivers realtime updates via Web PubSub, and the frontend analysis chat UI. This is the capstone task that delivers the AI-powered analysis capability.

## Why This Task Exists

AI-powered analysis is the primary differentiator. Without it, Integrisight.ai is a graph viewer. With it, users can ask questions about their integration landscape and get intelligent, data-backed answers. This task connects all previous work (graph, events, notifications) into a cohesive user experience.

## In Scope

- **AI Foundry infrastructure (Bicep):**
  - `Microsoft.CognitiveServices/accounts` (kind: `AIServices`, SKU: `S0`) — the Foundry resource
  - AI Foundry project within the AI Services account
  - Model deployment: GPT-4o, `GlobalStandard` SKU, 30K TPM (fallback to `Standard` if regional quota unavailable)
  - No private networking on Foundry resources for MVP (public network access enabled)
  - RBAC: worker managed identity gets `Cognitive Services User` role on the AI Services account
  - Bicep module: `infra/bicep/modules/ai-foundry.bicep`
  - Integration into `infra/bicep/main.bicep`
- Analysis API endpoints:
  - `POST /api/v1/projects/{id}/analyses` (request analysis)
  - `GET /api/v1/projects/{id}/analyses` (list analyses)
  - `GET /api/v1/projects/{id}/analyses/{analysisId}` (get result)
- Analysis domain module (router, service, models, repository)
- Cosmos DB `analyses` container
- Analysis worker:
  - Consumes `AnalysisRequested` events
  - Uses Microsoft Agent Framework SDK (`agent-framework` package) with `AIProjectClient`
  - Creates integration-analyst agent with `FunctionTool` definitions (auto-generated from Python type hints)
  - Creates quality-evaluator agent (no tools) that validates analyst responses against tool call evidence
  - Orchestrates analyst → evaluator flow with up to 1 retry on FAILED evaluation
  - Stores analysis result with evaluation metadata in Cosmos DB
  - Publishes `AnalysisCompleted` / `AnalysisFailed` events
- Four custom tools (implemented as typed Python functions for `FunctionTool`):
  - `get_project_summary`
  - `get_graph_neighbors`
  - `get_component_details`
  - `run_impact_analysis`
- Tenant/project scoping enforcement in all tool invocations
- Quality evaluator agent:
  - Receives user prompt, analyst response, and tool call history
  - Returns structured verdict: `{ verdict, confidence, issues, summary }`
  - On FAILED verdict (retry count < 1): evaluator issues fed back to analyst for revision
- Notification worker:
  - Consumes all terminal events
  - Sends realtime messages via Web PubSub
- Web PubSub integration:
  - Token negotiation endpoint (`POST /api/v1/realtime/negotiate`)
  - Client-side WebSocket connection
  - Cache invalidation on notification receipt
- Frontend:
  - Analysis chat page
  - Analysis history
  - Realtime notification integration (toasts, query invalidation)
  - Usage indicator (daily analysis quota)
- Quota enforcement for daily analysis count

## Out of Scope

- Additional specialized agents beyond analyst + evaluator (future scope)
- Streaming responses from the agent
- Custom user prompt templates (future feature)
- Agent conversation memory across sessions
- Private networking for Foundry resources (deferred to post-MVP)
- Offline evaluation pipelines, benchmarking datasets, or scoring dashboards
- Human-in-the-loop review workflows for evaluation

## Dependencies

- **Task 009** (graph builder): Graph data in Cosmos DB, GraphService for tool queries.
- **Task 007** (eventing foundation): Worker base class, event consumer/publisher.
- **Task 004** (tenancy/auth): Quota enforcement for daily analysis count.
- **Task 003** (frontend foundation): React Query, realtime provider stub.

## Files/Directories Expected to Be Created or Modified

```
infra/bicep/
├── modules/
│   └── ai-foundry.bicep           # AI Services account + project + GPT-4o model deployment
├── main.bicep                     # Updated: add AI Foundry module, RBAC for worker identity
src/backend/
├── domains/
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── router.py              # Analysis CRUD routes
│   │   ├── service.py             # AnalysisService
│   │   ├── models.py              # Analysis Pydantic models
│   │   └── repository.py          # Cosmos DB operations for analyses
│   └── realtime/
│       ├── __init__.py
│       ├── router.py              # Web PubSub negotiate endpoint
│       └── service.py             # RealtimeService (token generation)
├── workers/
│   ├── analysis/
│   │   ├── __init__.py
│   │   ├── main.py                # Entry point for analysis worker
│   │   ├── handler.py             # Analysis event handler
│   │   ├── agent.py               # Agent Framework: analyst + evaluator agent setup
│   │   ├── evaluator.py           # Quality evaluator agent definition and prompt
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── scoping.py         # Tenant/project scoping context for tool invocations
│   │       ├── get_project_summary.py   # Typed Python function for FunctionTool
│   │       ├── get_graph_neighbors.py   # Typed Python function for FunctionTool
│   │       ├── get_component_details.py # Typed Python function for FunctionTool
│   │       └── run_impact_analysis.py   # Typed Python function for FunctionTool
│   └── notification/
│       ├── __init__.py
│       ├── main.py                # Entry point for notification worker
│       └── handler.py             # Notification event handler
├── shared/
│   └── pubsub.py                  # Web PubSub client wrapper
├── main.py                        # Updated: register analysis and realtime routers
src/frontend/
├── src/
│   ├── app/(dashboard)/projects/[projectId]/analysis/
│   │   └── page.tsx               # Analysis chat page
│   ├── components/
│   │   ├── analysis/
│   │   │   ├── analysis-chat.tsx   # Chat UI component
│   │   │   ├── analysis-message.tsx # Single message display
│   │   │   └── analysis-history.tsx # Past analyses sidebar
│   │   ├── realtime/
│   │   │   ├── realtime-provider.tsx  # Updated: real Web PubSub connection
│   │   │   └── notification-toast.tsx  # Toast notifications
│   │   └── usage/
│   │       ├── usage-bar.tsx       # Usage progress bar
│   │       └── usage-summary.tsx   # Tier limits overview
│   ├── hooks/
│   │   ├── use-analysis.ts        # React Query hooks for analysis
│   │   └── use-realtime.ts        # Updated: real Web PubSub hooks
│   └── lib/
│       └── realtime.ts            # Updated: Web PubSub client implementation
tests/backend/
├── test_analysis_api.py
├── test_analysis_worker.py
├── test_agent_tools.py
├── test_quality_evaluator.py
├── test_notification_worker.py
└── test_realtime_negotiate.py
```

## Implementation Notes

### Analysis API Endpoints

```python
@router.post("/api/v1/projects/{project_id}/analyses", status_code=202)
async def create_analysis(project_id: str, body: CreateAnalysisRequest, request: Request):
    tenant = request.state.tenant
    # Quota check: maxDailyAnalyses (handled by middleware)
    
    analysis = await analysis_service.create(
        tenant_id=tenant.id,
        project_id=project_id,
        prompt=body.prompt,
        requested_by=request.state.user_id,
    )
    
    # Publish AnalysisRequested event
    await event_publisher.publish(...)
    
    return ResponseEnvelope(data=analysis, meta=build_meta(request))
```

### AI Foundry Infrastructure (Bicep)

Bicep module `infra/bicep/modules/ai-foundry.bicep` provisions the Foundry resources:

```bicep
// AI Services account (Foundry resource)
resource aiServices 'Microsoft.CognitiveServices/accounts@2024-10-01' = {
  name: name
  location: location
  kind: 'AIServices'
  sku: { name: 'S0' }
  tags: tags
  properties: {
    publicNetworkAccess: 'Enabled'  // No private networking for MVP
    customSubDomainName: name
  }
}

// Model deployment — GPT-4o
resource modelDeployment 'Microsoft.CognitiveServices/accounts/deployments@2024-10-01' = {
  parent: aiServices
  name: 'gpt-4o'
  sku: {
    name: 'GlobalStandard'
    capacity: 30  // 30K TPM
  }
  properties: {
    model: {
      format: 'OpenAI'
      name: 'gpt-4o'
      version: '2024-11-20'
    }
  }
}
```

The `main.bicep` must:
- Add the AI Foundry module invocation
- Add `Cognitive Services User` role assignment for the worker managed identity on the AI Services account
- Output the AI Services endpoint for worker configuration

### Microsoft Agent Framework Integration

```python
# workers/analysis/agent.py
import os
from azure.ai.projects import AIProjectClient
from azure.ai.agents.models import FunctionTool, ToolSet, ListSortOrder
from azure.identity.aio import ManagedIdentityCredential, DefaultAzureCredential
from .tools import get_project_summary, get_graph_neighbors, get_component_details, run_impact_analysis
from .evaluator import EVALUATOR_SYSTEM_PROMPT

# Use async credentials — Agent Framework requires async patterns
credential = (
    DefaultAzureCredential()
    if os.getenv("ENVIRONMENT") == "development"
    else ManagedIdentityCredential()
)

project_client = AIProjectClient(
    endpoint=os.environ["FOUNDRY_PROJECT_ENDPOINT"],
    credential=credential,
)

# Define tools as FunctionTool — schemas auto-generated from Python type hints
functions = FunctionTool([get_project_summary, get_graph_neighbors, get_component_details, run_impact_analysis])
toolset = ToolSet()
toolset.add(functions)

# Create analyst agent
analyst = project_client.agents.create_agent(
    model=os.environ["FOUNDRY_MODEL_DEPLOYMENT_NAME"],
    name="integration-analyst",
    instructions=ANALYST_SYSTEM_PROMPT,
    toolset=toolset,
)

# Create evaluator agent (no tools — evaluates analyst output only)
evaluator = project_client.agents.create_agent(
    model=os.environ["FOUNDRY_MODEL_DEPLOYMENT_NAME"],
    name="quality-evaluator",
    instructions=EVALUATOR_SYSTEM_PROMPT,
)

async def run_analysis(user_prompt: str, context: AnalysisContext) -> AnalysisResult:
    # 1. Run analyst
    thread = project_client.agents.threads.create()
    project_client.agents.messages.create(thread_id=thread.id, role="user", content=user_prompt)
    run = project_client.agents.runs.create_and_process(thread_id=thread.id, agent_id=analyst.id)
    
    analyst_messages = project_client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
    analyst_response = extract_response(analyst_messages)
    tool_call_history = extract_tool_calls(run)
    
    # 2. Run evaluator
    eval_result = await evaluate_response(user_prompt, analyst_response, tool_call_history)
    
    # 3. Retry once if FAILED
    if eval_result["verdict"] == "FAILED" and context.retry_count < 1:
        revision_prompt = f"Your previous response had issues: {eval_result['issues']}. Please revise."
        project_client.agents.messages.create(thread_id=thread.id, role="user", content=revision_prompt)
        run = project_client.agents.runs.create_and_process(thread_id=thread.id, agent_id=analyst.id)
        analyst_messages = project_client.agents.messages.list(thread_id=thread.id, order=ListSortOrder.ASCENDING)
        analyst_response = extract_response(analyst_messages)
        tool_call_history = extract_tool_calls(run)
        eval_result = await evaluate_response(user_prompt, analyst_response, tool_call_history)
    
    return AnalysisResult(
        response=analyst_response,
        tool_calls=tool_call_history,
        evaluation=eval_result,
    )
```

### Quality Evaluator Agent

```python
# workers/analysis/evaluator.py
EVALUATOR_SYSTEM_PROMPT = """
You are a quality evaluator for Integrisight.ai analysis responses.

You review the integration analyst's response and verify it against the tool call evidence provided.

You receive:
1. The user's original question.
2. The analyst's response.
3. The complete list of tool calls and their outputs.

Rules:
- Check that every component name, ID, count, and relationship cited in the response appears in the tool call outputs.
- Check that the response actually answers the user's question.
- If the response fabricates data not present in tool outputs, mark it as FAILED with specific citations.
- If the response is accurate but incomplete, mark it as PASSED with a note.
- If the response is accurate and complete, mark it as PASSED.

Return ONLY a JSON object:
{
  "verdict": "PASSED" or "FAILED",
  "confidence": 0.0 to 1.0,
  "issues": ["list of specific issues, empty if PASSED"],
  "summary": "one-sentence evaluation summary"
}
"""
```

### Custom Tool Implementation (FunctionTool Pattern)

Tools are implemented as typed Python functions. The Agent Framework `FunctionTool` auto-generates JSON schemas from type hints and docstrings. Tenant/project scoping is injected via a module-level context variable, not via function parameters.

```python
# workers/analysis/tools/scoping.py
from dataclasses import dataclass
import contextvars

@dataclass(frozen=True)
class AnalysisContext:
    tenant_id: str
    project_id: str

# Set by the worker before agent invocation, read by tool functions
analysis_context: contextvars.ContextVar[AnalysisContext] = contextvars.ContextVar("analysis_context")
```

```python
# workers/analysis/tools/run_impact_analysis.py
from .scoping import analysis_context

async def run_impact_analysis(component_id: str, direction: str, max_depth: int = 3) -> dict:
    """Perform a breadth-first traversal from a component to find all transitively dependent components.
    
    Args:
        component_id: The component ID to start traversal from.
        direction: Traversal direction — 'downstream' or 'upstream'.
        max_depth: Maximum traversal depth (default 3, capped at 5).
    
    Returns:
        Dictionary with rootComponent, impactedComponents list, and totalImpacted count.
    """
    ctx = analysis_context.get()
    max_depth = min(max_depth, 5)  # Cap at 5
    
    impacted = await graph_service.traverse(
        ctx.tenant_id, ctx.project_id, component_id, direction, max_depth
    )
    return {"rootComponent": ..., "impactedComponents": impacted, "totalImpacted": len(impacted)}
```

### Notification Worker

```python
class NotificationHandler:
    NOTIFICATION_MAP = {
        EVENT_ARTIFACT_SCAN_PASSED: "artifact.status_changed",
        EVENT_ARTIFACT_SCAN_FAILED: "artifact.status_changed",
        EVENT_ARTIFACT_PARSED: "artifact.status_changed",
        EVENT_ARTIFACT_PARSE_FAILED: "artifact.status_changed",
        EVENT_GRAPH_UPDATED: "graph.updated",
        EVENT_GRAPH_BUILD_FAILED: "graph.build_failed",
        EVENT_ANALYSIS_COMPLETED: "analysis.completed",
        EVENT_ANALYSIS_FAILED: "analysis.failed",
    }
    
    async def handle(self, event_data: dict):
        event_type = event_data.get("_event_type")
        notification_type = self.NOTIFICATION_MAP.get(event_type)
        if not notification_type:
            return
        
        tenant_id = event_data["tenantId"]
        project_id = event_data.get("projectId")
        
        # Send to tenant group
        await self.pubsub_service.send_to_group(
            group=f"tenant:{tenant_id}",
            data={"type": notification_type, "data": self._build_payload(event_data)},
        )
        
        # Send to project group if applicable
        if project_id:
            await self.pubsub_service.send_to_group(
                group=f"project:{tenant_id}:{project_id}",
                data={"type": notification_type, "data": self._build_payload(event_data)},
            )
```

### Web PubSub Token Negotiation

```python
# domains/realtime/router.py
@router.post("/api/v1/realtime/negotiate")
async def negotiate(request: Request):
    tenant = request.state.tenant
    user_id = request.state.user_id
    
    token = await realtime_service.generate_client_token(
        user_id=user_id,
        groups=[f"tenant:{tenant.id}"],
    )
    
    return ResponseEnvelope(data={"url": token.url}, meta=build_meta(request))
```

### Frontend Analysis Chat

The analysis chat page provides:
1. **Chat input**: Text field for typing analysis prompts.
2. **Analysis submission**: Calls `POST /analyses` and shows "Analyzing..." state.
3. **Realtime result**: Receives `AnalysisCompleted` notification → fetches result → displays.
4. **Analysis history**: Sidebar listing past analyses for the project.
5. **Usage indicator**: "X of Y daily analyses remaining."

### Frontend Realtime Integration

Update the realtime provider stub from task 003 with actual Web PubSub connection:
1. On mount, call `POST /realtime/negotiate` to get WebSocket URL.
2. Connect to Web PubSub.
3. On message, determine event type and invalidate relevant React Query cache keys.
4. Show toast notifications for key events.

## Acceptance Criteria

### Infrastructure
- [ ] AI Services account is provisioned via Bicep with `kind: AIServices`, SKU `S0`
- [ ] GPT-4o model is deployed with `GlobalStandard` SKU and 30K TPM capacity
- [ ] Worker managed identity has `Cognitive Services User` role on the AI Services account
- [ ] AI Foundry module integrates cleanly into `main.bicep`
- [ ] AI Services endpoint is output from `main.bicep` for worker configuration

### Analysis API
- [ ] `POST /api/v1/projects/{id}/analyses` creates an analysis and returns 202
- [ ] Quota enforcement: daily analysis limit returns 429
- [ ] `GET /analyses/{id}` returns the analysis result
- [ ] `AnalysisCompleted` event is published

### Agent Framework & Agents
- [ ] Microsoft Agent Framework SDK is used (not raw thread/run polling)
- [ ] Integration-analyst agent is created with `FunctionTool` definitions
- [ ] Quality-evaluator agent validates analyst responses against tool call evidence
- [ ] Failed evaluations trigger one analyst retry with evaluator feedback
- [ ] Analysis result includes evaluation metadata (verdict, confidence, issues, retryCount)
- [ ] All four custom tools are registered and callable by the analyst agent
- [ ] Tools enforce tenant/project scoping (cannot query other tenants)
- [ ] `get_project_summary` returns graph summary data
- [ ] `get_graph_neighbors` returns neighbors for a component
- [ ] `get_component_details` returns component details
- [ ] `run_impact_analysis` performs BFS traversal and returns results
- [ ] Analysis result is stored in Cosmos DB

### Realtime & Notifications
- [ ] Notification worker sends Web PubSub messages for all terminal events
- [ ] `POST /realtime/negotiate` returns a valid Web PubSub client token
- [ ] Frontend receives realtime notifications and invalidates queries

### Frontend
- [ ] Frontend analysis chat shows prompt input, loading state, and result
- [ ] Frontend shows toast notifications for key events
- [ ] Usage indicator shows daily analysis quota

### End-to-End
- [ ] End-to-end flow: prompt → analyst → evaluator → result → notification → UI update

## Definition of Done

- The full MVP pipeline works end-to-end: upload → scan → parse → graph → analyze.
- Users can ask questions about their integration landscape and get intelligent answers.
- Realtime notifications keep the UI in sync with background processing.
- Tenant isolation is enforced at every layer.
- The MVP is feature-complete.

## Risks / Gotchas

- **Microsoft Agent Framework SDK**: The `agent-framework` package may be in pre-release. Pin a specific version in `pyproject.toml`. Use `azure.identity.aio` for async credentials (not `azure.identity`).
- **Model deployment quota**: `GlobalStandard` GPT-4o may not have capacity in all regions. Fall back to `Standard` SKU if regional quota is unavailable. Use `infra/bicep/environments/` parameter files to make SKU configurable per environment.
- **Foundry project provisioning**: AI Services account + project creation via Bicep may take several minutes. Ensure deployment scripts account for this.
- **Tool call latency**: Multiple tool calls per analysis may add up. Set a reasonable timeout (60s per analysis).
- **Web PubSub connection lifecycle**: Handle WebSocket disconnects and reconnects in the frontend.
- **Cost**: Foundry Agent Service calls cost money. The quality evaluator adds ~1 extra LLM call per analysis (and up to 2 more on retry). Ensure the daily analysis quota is enforced to prevent runaway costs.
- **Agent hallucination**: The quality evaluator agent mitigates this programmatically, but the analyst system prompt must still clearly instruct the agent to use tools and not fabricate data. Test with adversarial prompts.
- **Eval agent reliability**: The evaluator itself uses an LLM and could occasionally mis-judge. The structured JSON output format and low temperature (0.1) minimize this risk.

## Suggested Validation Steps

1. Deploy Bicep: verify AI Services account, project, and GPT-4o deployment are provisioned.
2. Verify worker managed identity has `Cognitive Services User` on the AI Services account.
3. Create an analysis: `POST /api/v1/projects/{id}/analyses` with a prompt.
4. Verify analysis worker picks up the event and invokes Foundry via Agent Framework.
5. Check Cosmos DB: analysis document should have status `completed` with result and `evaluation` metadata.
6. Verify evaluation metadata includes `verdict`, `confidence`, `issues`, and `retryCount`.
7. Call `GET /analyses/{id}` → verify result with evaluation data is returned.
8. Test each tool individually with mock agent calls.
9. Verify tenant scoping: tool should only return data for the correct tenant/project.
10. Test evaluator: submit a prompt that would trigger hallucination → verify evaluator catches it and triggers retry.
11. Test notification worker: publish a terminal event → verify Web PubSub message.
12. Open frontend, submit an analysis → verify chat shows loading, then result.
13. Verify toast notifications appear for artifact status changes.
14. Test quota: exhaust daily analysis limit → verify 429 response.
15. Run all tests: `uv run pytest tests/backend/ -v`
