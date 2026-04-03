# Prompt — Execute Task 008: Parser Worker

You are an expert Python backend engineer. Execute the following task to implement the artifact parser worker for Integrisight.ai.

## Context

Read these documents before starting:

- **Task spec**: `docs/plan/tasks/008-parser-worker.md`
- **Graph and metadata domain**: `docs/plan/04-domain-graph-and-metadata.md`
- **Projects and artifacts domain**: `docs/plan/03-domain-projects-and-artifacts.md`
- **Eventing and processing**: `docs/plan/05-domain-eventing-and-processing.md`

**Prerequisites**: Tasks 005 (artifact domain), 006 (upload flow), and 007 (eventing foundation) must be complete. The worker base class, Event Grid consumer, artifact state machine, and Blob Storage access must be working.

## What You Must Do

Build the parser worker with three artifact parsers (Logic App, OpenAPI, APIM Policy) that extract components and edges from raw files and store structured parse results in Cosmos DB.

### Step 1 — Parse Result Models

Create `src/backend/workers/parser/models.py`:
- `ParsedComponent` — temp_id, component_type, name, display_name, properties (dict)
- `ParsedEdge` — source_temp_id, target_temp_id, edge_type, properties (dict | None)
- `ExternalReference` — temp_id, component_type (always `"external_service"`), name, display_name, inferred_from
- `ParseResult` — artifact_id, artifact_type, components (list), edges (list), external_references (list), parsed_at

### Step 2 — Base Parser Interface

Create `src/backend/workers/parser/parsers/base.py`:
- Abstract base class `BaseParser` with `parse(content: bytes, filename: str) -> ParseResult`.

### Step 3 — Logic App Workflow Parser

Create `src/backend/workers/parser/parsers/logic_app.py` — `LogicAppParser(BaseParser)`:
- Parse the `definition` property from the JSON (or the root if `definition` is absent).
- Extract one `logic_app_workflow` component per file (properties: trigger type, action count).
- Extract one `logic_app_trigger` per trigger in `definition.triggers`.
- Extract one `logic_app_action` per action in `definition.actions` (properties: action type, method, URI for HTTP).
- Create edges: workflow → triggers (`triggers` type), workflow → actions (`calls` type), action → action based on `runAfter`.
- Infer external references from HTTP action URIs and Service Bus connections.

### Step 4 — OpenAPI Spec Parser

Create `src/backend/workers/parser/parsers/openapi.py` — `OpenApiParser(BaseParser)`:
- Support both OpenAPI v3 (`openapi: 3.x`) and Swagger v2 (`swagger: "2.0"`), JSON and YAML.
- Extract one `api_definition` component (properties: title, version, base URL, operation count).
- Extract one `api_operation` per path + method (properties: method, path, summary).
- Create edges: api_definition → each operation (`has_operation` type).
- Infer external references from `servers` (v3) or `host`/`basePath` (v2).

### Step 5 — APIM Policy XML Parser

Create `src/backend/workers/parser/parsers/apim_policy.py` — `ApimPolicyParser(BaseParser)`:
- Parse the `<policies>` XML root using `xml.etree.ElementTree`.
- Extract `apim_policy` components for each section (inbound, outbound, backend, on-error).
- Extract policy names within sections (rate-limit, cors, set-header, etc.).
- Create edges to referenced backends (`depends_on` type).
- Infer external references from backend service URLs.

### Step 6 — Parser Registry

Create `src/backend/workers/parser/parsers/__init__.py`:
```python
PARSER_REGISTRY = {
    "logic_app_workflow": LogicAppParser(),
    "openapi_spec": OpenApiParser(),
    "apim_policy": ApimPolicyParser(),
}

def get_parser(artifact_type: str) -> BaseParser:
    parser = PARSER_REGISTRY.get(artifact_type)
    if not parser:
        raise UnsupportedArtifactType(artifact_type)
    return parser
```

### Step 7 — Parser Worker Handler

Create `src/backend/workers/parser/handler.py` — `ParserHandler`:
- `is_already_processed(event_data)` — True if artifact status is `parsed` or beyond.
- `handle(event_data)`:
  1. Transition artifact to `parsing`.
  2. Download raw artifact from Blob Storage using `blobPath` from event data.
  3. Get parser from registry based on `artifactType`.
  4. Call `parser.parse(content, filename)`.
  5. Store parse result as a document in Cosmos DB `projects` container.
  6. Update artifact status to `parsed` with `parseResult` summary (componentCount, edgeCount, parsedAt).
  7. Publish `ArtifactParsed` event.
- `handle_failure(event_data, error)` — transition to `parse_failed`, publish `ArtifactParseFailed`.

### Step 8 — Worker Entry Point

Create `src/backend/workers/parser/main.py`:
- Create consumer (subscription: `"artifact-parser"`, topic: `"integration-events"`).
- Create handler with artifact repo, blob service, event publisher.
- Create `BaseWorker` and run.

### Step 9 — Test Fixtures

Create test fixture files under `tests/backend/fixtures/`:
- `logic_app_workflow.json` — a realistic Logic App workflow with triggers, HTTP actions, and Service Bus actions.
- `openapi_v3.json` — an OpenAPI v3 spec with multiple operations.
- `openapi_v3.yaml` — same spec in YAML format.
- `apim_policy.xml` — an APIM policy with inbound, outbound, and backend sections.

### Step 10 — Tests

- `tests/backend/test_logic_app_parser.py` — test component/edge extraction from the fixture.
- `tests/backend/test_openapi_parser.py` — test v2 and v3, JSON and YAML.
- `tests/backend/test_apim_policy_parser.py` — test policy component extraction.
- `tests/backend/test_parser_worker.py` — test the handler end-to-end with mocks.

### Step 11 — Validation

1. Upload a Logic App JSON → verify scan → parse pipeline completes.
2. Check Cosmos DB for parse result document with components and edges.
3. Upload OpenAPI v3 JSON → verify API definition and operations extracted.
4. Upload OpenAPI v2 YAML → verify backward compatibility.
5. Upload APIM XML → verify policy components extracted.
6. Upload malformed JSON → verify `parse_failed` with error details.
7. `uv run pytest tests/backend/test_*parser*.py tests/backend/test_parser_worker.py -v` — all pass.

## Constraints

- Parsers are deterministic code — no LLM calls.
- Parsers must fail gracefully with clear error messages for malformed input.
- Handle files up to 10 MB without excessive memory usage.
- Parse results use temporary IDs (`temp_id`) — stable IDs are generated by the graph builder (task 009).
- Do not build the graph builder — only produce parse results.

## Done When

- All three parsers correctly extract components and edges from fixture files.
- Parse results are stored in Cosmos DB.
- The pipeline flows: upload → scan → parse automatically.
- Parse failures are handled with correct status transitions and events.
- All tests pass.
