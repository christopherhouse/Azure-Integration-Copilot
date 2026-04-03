# Task 010 — Foundry Agent, Tools, and Analysis Flow

## Title

Implement the Foundry Agent Service integration, custom tools, analysis worker, notification worker, and frontend analysis chat.

## Objective

Build the analysis flow end-to-end: API endpoints for requesting and viewing analyses, the analysis worker that invokes Azure AI Foundry Agent Service with custom tools, the notification worker that delivers realtime updates via Web PubSub, and the frontend analysis chat UI. This is the capstone task that delivers the AI-powered analysis capability.

## Why This Task Exists

AI-powered analysis is the primary differentiator. Without it, Integrisight.ai is a graph viewer. With it, users can ask questions about their integration landscape and get intelligent, data-backed answers. This task connects all previous work (graph, events, notifications) into a cohesive user experience.

## In Scope

- Analysis API endpoints:
  - `POST /api/v1/projects/{id}/analyses` (request analysis)
  - `GET /api/v1/projects/{id}/analyses` (list analyses)
  - `GET /api/v1/projects/{id}/analyses/{analysisId}` (get result)
- Analysis domain module (router, service, models, repository)
- Cosmos DB `analyses` container
- Analysis worker:
  - Consumes `AnalysisRequested` events
  - Invokes Foundry Agent Service with system prompt + user prompt
  - Registers and handles custom tool calls
  - Stores analysis result in Cosmos DB
  - Publishes `AnalysisCompleted` / `AnalysisFailed` events
- Four custom tools:
  - `get_project_summary`
  - `get_graph_neighbors`
  - `get_component_details`
  - `run_impact_analysis`
- Tenant/project scoping enforcement in all tool invocations
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

- Multiple agents (MVP has one agent)
- Streaming responses from the agent
- Custom user prompt templates (future feature)
- Agent conversation memory across sessions
- Foundry agent deployment automation (manual setup documented)

## Dependencies

- **Task 009** (graph builder): Graph data in Cosmos DB, GraphService for tool queries.
- **Task 007** (eventing foundation): Worker base class, event consumer/publisher.
- **Task 004** (tenancy/auth): Quota enforcement for daily analysis count.
- **Task 003** (frontend foundation): React Query, realtime provider stub.

## Files/Directories Expected to Be Created or Modified

```
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
│   │   ├── agent.py               # Foundry Agent Service client
│   │   └── tools/
│   │       ├── __init__.py
│   │       ├── base.py            # Tool base class with scoping enforcement
│   │       ├── get_project_summary.py
│   │       ├── get_graph_neighbors.py
│   │       ├── get_component_details.py
│   │       └── run_impact_analysis.py
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

### Foundry Agent Service Integration

```python
# workers/analysis/agent.py
from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential

class FoundryAgentClient:
    def __init__(self, project_connection_string: str):
        self.client = AIProjectClient.from_connection_string(
            conn_str=project_connection_string,
            credential=DefaultAzureCredential(),
        )
    
    async def run_analysis(
        self,
        agent_id: str,
        system_prompt: str,
        user_prompt: str,
        tools: list,
        tool_handler,
    ) -> AnalysisResult:
        # Create a thread
        thread = await self.client.agents.create_thread()
        
        # Add user message
        await self.client.agents.create_message(
            thread_id=thread.id,
            role="user",
            content=user_prompt,
        )
        
        # Run the agent
        run = await self.client.agents.create_run(
            thread_id=thread.id,
            agent_id=agent_id,
        )
        
        # Poll for completion, handle tool calls
        while run.status in ("queued", "in_progress", "requires_action"):
            if run.status == "requires_action":
                tool_outputs = await tool_handler.handle_tool_calls(run.required_action.submit_tool_outputs.tool_calls)
                run = await self.client.agents.submit_tool_outputs(
                    thread_id=thread.id,
                    run_id=run.id,
                    tool_outputs=tool_outputs,
                )
            else:
                await asyncio.sleep(1)
                run = await self.client.agents.get_run(thread_id=thread.id, run_id=run.id)
        
        # Get response
        messages = await self.client.agents.list_messages(thread_id=thread.id)
        return self._extract_result(messages, run)
```

### Custom Tool Implementation

```python
# workers/analysis/tools/base.py
class BaseTool:
    """Base class for agent tools with mandatory tenant/project scoping."""
    
    def __init__(self, graph_service):
        self.graph_service = graph_service
    
    async def execute(self, params: dict, context: AnalysisContext) -> dict:
        # ALWAYS use context for tenant/project scope, never params
        tenant_id = context.tenant_id
        project_id = context.project_id
        return await self._execute(params, tenant_id, project_id)
    
    async def _execute(self, params: dict, tenant_id: str, project_id: str) -> dict:
        raise NotImplementedError
```

```python
# workers/analysis/tools/run_impact_analysis.py
class RunImpactAnalysisTool(BaseTool):
    tool_definition = {
        "type": "function",
        "function": {
            "name": "run_impact_analysis",
            "description": "Perform a breadth-first traversal from a component to find all transitively dependent components.",
            "parameters": {
                "type": "object",
                "properties": {
                    "componentId": {"type": "string", "description": "The component to start from"},
                    "direction": {"type": "string", "enum": ["downstream", "upstream"], "description": "Traversal direction"},
                    "maxDepth": {"type": "integer", "description": "Maximum traversal depth", "default": 3},
                },
                "required": ["componentId", "direction"],
            },
        },
    }
    
    async def _execute(self, params: dict, tenant_id: str, project_id: str) -> dict:
        component_id = params["componentId"]
        direction = params["direction"]
        max_depth = min(params.get("maxDepth", 3), 5)  # Cap at 5
        
        # BFS traversal
        impacted = await self.graph_service.traverse(
            tenant_id, project_id, component_id, direction, max_depth
        )
        return {"rootComponent": ..., "impactedComponents": impacted, "totalImpacted": len(impacted)}
```

### Tool Handler (Scoping Enforcement)

```python
class ToolHandler:
    def __init__(self, tools: dict[str, BaseTool], context: AnalysisContext):
        self.tools = tools
        self.context = context  # Immutable tenant/project scope

    async def handle_tool_calls(self, tool_calls: list) -> list:
        outputs = []
        for call in tool_calls:
            tool = self.tools.get(call.function.name)
            if not tool:
                outputs.append({"tool_call_id": call.id, "output": json.dumps({"error": "Unknown tool"})})
                continue
            
            params = json.loads(call.function.arguments)
            result = await tool.execute(params, self.context)  # Context enforces scoping
            outputs.append({"tool_call_id": call.id, "output": json.dumps(result)})
        return outputs
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

- [ ] `POST /api/v1/projects/{id}/analyses` creates an analysis and returns 202
- [ ] Quota enforcement: daily analysis limit returns 429
- [ ] Analysis worker invokes Foundry Agent Service with correct system prompt
- [ ] All four custom tools are registered and callable by the agent
- [ ] Tools enforce tenant/project scoping (cannot query other tenants)
- [ ] `get_project_summary` returns graph summary data
- [ ] `get_graph_neighbors` returns neighbors for a component
- [ ] `get_component_details` returns component details
- [ ] `run_impact_analysis` performs BFS traversal and returns results
- [ ] Analysis result is stored in Cosmos DB
- [ ] `GET /analyses/{id}` returns the analysis result
- [ ] `AnalysisCompleted` event is published
- [ ] Notification worker sends Web PubSub messages for all terminal events
- [ ] `POST /realtime/negotiate` returns a valid Web PubSub client token
- [ ] Frontend receives realtime notifications and invalidates queries
- [ ] Frontend analysis chat shows prompt input, loading state, and result
- [ ] Frontend shows toast notifications for key events
- [ ] Usage indicator shows daily analysis quota
- [ ] End-to-end flow: prompt → analysis → result → notification → UI update

## Definition of Done

- The full MVP pipeline works end-to-end: upload → scan → parse → graph → analyze.
- Users can ask questions about their integration landscape and get intelligent answers.
- Realtime notifications keep the UI in sync with background processing.
- Tenant isolation is enforced at every layer.
- The MVP is feature-complete.

## Risks / Gotchas

- **Foundry Agent Service SDK**: Ensure the correct SDK version and region availability. The SDK may be in preview.
- **Agent setup**: The agent must be created in Foundry before the worker can invoke it. Document the manual setup steps.
- **Tool call latency**: Multiple tool calls per analysis may add up. Set a reasonable timeout (60s per analysis).
- **Web PubSub connection lifecycle**: Handle WebSocket disconnects and reconnects in the frontend.
- **Cost**: Foundry Agent Service calls cost money. Ensure the daily analysis quota is enforced to prevent runaway costs.
- **Agent hallucination**: The system prompt must clearly instruct the agent to use tools and not fabricate data. Test with adversarial prompts.

## Suggested Validation Steps

1. Create an analysis: `POST /api/v1/projects/{id}/analyses` with a prompt.
2. Verify analysis worker picks up the event and invokes Foundry.
3. Check Cosmos DB: analysis document should have status `completed` with result.
4. Call `GET /analyses/{id}` → verify result is returned.
5. Test each tool individually with mock agent calls.
6. Verify tenant scoping: tool should only return data for the correct tenant/project.
7. Test notification worker: publish a terminal event → verify Web PubSub message.
8. Open frontend, submit an analysis → verify chat shows loading, then result.
9. Verify toast notifications appear for artifact status changes.
10. Test quota: exhaust daily analysis limit → verify 429 response.
11. Run all tests: `uv run pytest tests/backend/ -v`
