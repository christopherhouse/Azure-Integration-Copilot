# Prompt — Execute Task 010: Foundry Agent, Tools, and Analysis Flow

You are an expert Python backend and frontend engineer. Execute the following task to implement the AI analysis flow, notification system, and analysis chat UI for Integration Copilot.

## Context

Read these documents before starting:

- **Task spec**: `docs/plan/tasks/010-foundry-agent-tools-and-analysis-flow.md`
- **Agents and tools domain**: `docs/plan/06-domain-agents-and-tools.md`
- **Eventing and processing**: `docs/plan/05-domain-eventing-and-processing.md`
- **Frontend UX**: `docs/plan/08-frontend-and-ux.md`
- **API design**: `docs/plan/07-api-design.md`

**Prerequisites**: Tasks 004 (tenancy/auth), 007 (eventing), and 009 (graph builder) must be complete. Graph data must be queryable, the worker base class must be operational, and quota enforcement must be in place.

## What You Must Do

Build the complete analysis flow: API endpoints, analysis worker with Foundry Agent Service integration, four custom tools, notification worker with Web PubSub, and the frontend analysis chat.

### Step 1 — Analysis Domain Module

Create `src/backend/domains/analysis/`:
- `models.py`:
  - `CreateAnalysisRequest` — prompt (str, required)
  - `AnalysisResponse` — id, project_id, prompt, status (`pending`, `in_progress`, `completed`, `failed`), result (response text, tool_calls, duration_ms, tokens_used), requested_by, created_at, completed_at
- `repository.py` — Cosmos DB operations for `analyses` container (partition key: `{tenantId}`)
- `service.py` — `AnalysisService` with create, get, list methods
- `router.py`:
  - `POST /api/v1/projects/{projectId}/analyses` — create analysis, publish `AnalysisRequested` event, return 202. Quota middleware checks `max_daily_analyses`.
  - `GET /api/v1/projects/{projectId}/analyses` — list analyses for project (paginated).
  - `GET /api/v1/projects/{projectId}/analyses/{analysisId}` — get analysis result.

### Step 2 — Realtime Domain Module

Create `src/backend/domains/realtime/`:
- `router.py`:
  - `POST /api/v1/realtime/negotiate` — generate a Web PubSub client access token scoped to the tenant's groups (`tenant:{tenantId}`). Return `{ "url": "wss://..." }`.
- `service.py` — `RealtimeService` using Web PubSub management SDK.

Create `src/backend/shared/pubsub.py` — Web PubSub client wrapper using managed identity.

Register both routers in `main.py`.

### Step 3 — Custom Agent Tools

Create `src/backend/workers/analysis/tools/`:
- `base.py` — `BaseTool` with `execute(params, context)` that enforces tenant/project scoping via an immutable `AnalysisContext` (never trusts params for scope).
- `get_project_summary.py` — queries `GraphService.get_summary()`. Returns project name, graph version, component/edge counts.
- `get_graph_neighbors.py` — queries `GraphService.get_neighbors()`. Input: componentId, direction (both/incoming/outgoing). Returns component with its neighbors.
- `get_component_details.py` — queries `GraphService.get_component()`. Returns full component details with edge counts.
- `run_impact_analysis.py` — BFS traversal via `GraphService.traverse()`. Input: componentId, direction (downstream/upstream), maxDepth (default 3, cap 5). Returns impacted components with paths.

Each tool includes a `tool_definition` dict matching the Foundry function-calling schema.

### Step 4 — Foundry Agent Service Client

Create `src/backend/workers/analysis/agent.py`:
- `FoundryAgentClient` class using `azure-ai-projects` SDK with `DefaultAzureCredential`.
- `run_analysis(agent_id, system_prompt, user_prompt, tools, tool_handler)`:
  1. Create a thread.
  2. Add the user message.
  3. Create a run with the agent.
  4. Poll for completion, handling `requires_action` status by dispatching tool calls to `tool_handler`.
  5. Return the final response with tool call details.

Add `azure-ai-projects` to dependencies.

### Step 5 — Analysis Worker

Create `src/backend/workers/analysis/`:
- `handler.py` — `AnalysisHandler`:
  - `is_already_processed()` — True if analysis status is `completed`.
  - `handle(event_data)`:
    1. Update analysis status to `in_progress`.
    2. Load project context (graph summary).
    3. Build system prompt with tenant/project context and graph stats.
    4. Create `ToolHandler` with the four tools and immutable `AnalysisContext`.
    5. Invoke `FoundryAgentClient.run_analysis()`.
    6. Store result in Cosmos DB (status: `completed`, response, tool calls, duration).
    7. Publish `AnalysisCompleted` event.
  - `handle_failure()` — set status to `failed`, publish `AnalysisFailed`.
- `main.py` — entry point (subscription: `"analysis-execution"`, topic: `"integration-events"`).

### Step 6 — Tool Handler (Scoping Enforcement)

Create `src/backend/workers/analysis/handler.py` (or separate file):
- `ToolHandler` class that:
  - Maps tool names to `BaseTool` instances.
  - Receives tool calls from the agent run.
  - Calls `tool.execute(params, context)` where context is the immutable tenant/project scope.
  - Returns results as JSON strings.
  - **Never allows the LLM to choose which tenant/project to query.**

### Step 7 — Notification Worker

Create `src/backend/workers/notification/`:
- `handler.py` — `NotificationHandler`:
  - Maps terminal event types to notification types (artifact status changes, graph updates, analysis results).
  - Sends Web PubSub messages to `tenant:{tenantId}` and `project:{tenantId}:{projectId}` groups.
  - Payload format: `{ "type": "...", "data": { ... } }`.
- `main.py` — entry point (subscription: `"notification"`, topic: `"integration-events"`).

### Step 8 — Frontend Analysis Chat

Create:
- `src/frontend/src/app/(dashboard)/projects/[projectId]/analysis/page.tsx` — analysis chat page.
- `src/frontend/src/components/analysis/analysis-chat.tsx` — chat interface with prompt input, loading spinner, and result display.
- `src/frontend/src/components/analysis/analysis-message.tsx` — individual message rendering (user prompt and agent response).
- `src/frontend/src/components/analysis/analysis-history.tsx` — sidebar with past analyses.
- `src/frontend/src/hooks/use-analysis.ts` — React Query hooks for creating, listing, and fetching analyses.

### Step 9 — Frontend Realtime Integration

Update the realtime provider from task 003:
- `src/frontend/src/components/providers/realtime-provider.tsx` — connect to Web PubSub using token from `POST /realtime/negotiate`.
- `src/frontend/src/hooks/use-realtime.ts` — on message, invalidate relevant React Query cache keys.
- `src/frontend/src/components/realtime/notification-toast.tsx` — show toast notifications for key events.

### Step 10 — Usage Indicators

Create:
- `src/frontend/src/components/usage/usage-bar.tsx` — progress bar showing usage vs limit.
- `src/frontend/src/components/usage/usage-summary.tsx` — tier limits overview.
- Add daily analysis quota indicator to the analysis page.

### Step 11 — Tests

- `tests/backend/test_analysis_api.py` — test analysis CRUD endpoints.
- `tests/backend/test_analysis_worker.py` — test handler with mocked Foundry client.
- `tests/backend/test_agent_tools.py` — test each tool with tenant scoping enforcement.
- `tests/backend/test_notification_worker.py` — test notification mapping and Web PubSub calls.
- `tests/backend/test_realtime_negotiate.py` — test token generation endpoint.

### Step 12 — Validation

1. `POST /api/v1/projects/{id}/analyses` with `{ "prompt": "What breaks if the Order API goes down?" }` → 202.
2. Analysis worker invokes Foundry and calls tools.
3. `GET /analyses/{id}` → completed result with response text and tool call details.
4. Verify tenant scoping: tools only return data for the correct tenant/project.
5. Notification worker sends Web PubSub messages for all terminal events.
6. `POST /realtime/negotiate` → valid WebSocket URL.
7. Frontend: submit analysis → loading state → result displayed.
8. Frontend: toast notifications appear for status changes.
9. Test quota: exhaust daily limit → 429 response.
10. `uv run pytest tests/backend/ -v` — all tests pass.

## Constraints

- Use Azure AI Foundry Agent Service with real tool definitions — no simulated agent behavior.
- Tools always use the immutable context for tenant/project scoping, never LLM-provided parameters.
- The agent system prompt must instruct the agent to use tools and not fabricate data.
- Set a 60-second timeout per analysis.
- Notifications are invalidation signals — the frontend fetches updated data from the API.
- Do not implement streaming, multi-agent, or conversation memory.
- Add `azure-ai-projects` and `azure-messaging-webpubsubservice` to dependencies.

## Done When

- The full MVP pipeline works end-to-end: upload → scan → parse → graph → analyze.
- Users can ask questions and get intelligent, data-backed answers.
- Realtime notifications keep the UI in sync.
- Tenant isolation is enforced at every layer.
- All tests pass.
- The MVP is feature-complete.
