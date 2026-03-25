# Task 008 — Parser Worker

## Title

Implement the parser worker with Logic App, OpenAPI, and APIM policy parsers.

## Objective

Build the parser worker that consumes `ArtifactScanPassed` events, downloads raw artifacts from Blob Storage, runs type-specific parsers to extract components and edges, stores parse results in Cosmos DB, and publishes `ArtifactParsed` events. This is the critical step that transforms raw files into structured graph data.

## Why This Task Exists

The dependency graph is the core value of Integration Copilot. The graph is only as good as the parsing. This task implements the deterministic parsing that extracts structure from raw artifacts — the foundation that the agent reasons over.

## In Scope

- Parser worker using the worker base class from task 007
- Logic App workflow JSON parser
- OpenAPI specification parser (JSON and YAML, v2 and v3)
- APIM policy XML parser
- Parse result data model and storage in Cosmos DB
- Artifact status transitions: `scan_passed` → `parsing` → `parsed` (or `parse_failed`)
- `ArtifactParsed` / `ArtifactParseFailed` event publishing
- Component and edge extraction with temporary IDs
- External service inference (referenced but undefined endpoints)
- Error handling for malformed or unexpected artifact content

## Out of Scope

- Graph builder (task 009) — this task produces parse results, not graph documents
- Terraform/Bicep parsers (stretch scope)
- Frontend changes
- Parser configuration UI

## Dependencies

- **Task 007** (eventing foundation): Worker base class, Event Grid consumer, CloudEvents builder.
- **Task 006** (upload flow): Artifacts in Blob Storage, `ArtifactScanPassed` events.
- **Task 005** (artifact domain): Artifact status state machine, Cosmos DB repository.

## Files/Directories Expected to Be Created or Modified

```
src/backend/
├── workers/
│   └── parser/
│       ├── __init__.py
│       ├── main.py                # Entry point for parser worker
│       ├── handler.py             # Parser event handler
│       ├── parsers/
│       │   ├── __init__.py
│       │   ├── base.py            # Base parser interface
│       │   ├── logic_app.py       # Logic App workflow parser
│       │   ├── openapi.py         # OpenAPI spec parser
│       │   └── apim_policy.py     # APIM policy XML parser
│       └── models.py              # ParseResult, ParsedComponent, ParsedEdge
tests/backend/
├── test_parser_worker.py
├── test_logic_app_parser.py
├── test_openapi_parser.py
├── test_apim_policy_parser.py
└── fixtures/
    ├── logic_app_workflow.json
    ├── openapi_v3.json
    ├── openapi_v3.yaml
    └── apim_policy.xml
```

## Implementation Notes

### Parse Result Model

```python
# workers/parser/models.py
class ParsedComponent:
    temp_id: str              # Temporary ID for linking edges within this parse
    component_type: str       # e.g., "logic_app_workflow", "api_operation"
    name: str                 # Canonical name for ID generation
    display_name: str         # Human-readable name
    properties: dict          # Type-specific properties

class ParsedEdge:
    source_temp_id: str
    target_temp_id: str
    edge_type: str            # e.g., "calls", "has_operation"
    properties: dict | None

class ExternalReference:
    temp_id: str
    component_type: str       # Always "external_service"
    name: str                 # Canonical name (e.g., hostname)
    display_name: str
    inferred_from: str        # How this was detected

class ParseResult:
    artifact_id: str
    artifact_type: str
    components: list[ParsedComponent]
    edges: list[ParsedEdge]
    external_references: list[ExternalReference]
    parsed_at: datetime
```

### Base Parser Interface

```python
# workers/parser/parsers/base.py
from abc import ABC, abstractmethod

class BaseParser(ABC):
    @abstractmethod
    def parse(self, content: bytes, filename: str) -> ParseResult:
        """Parse raw artifact content into components and edges."""
        pass
```

### Logic App Workflow Parser

Extracts from a Logic App `definition` JSON:

1. **Workflow component**: One `logic_app_workflow` component per file.
   - Properties: trigger type, action count, has retry policy.
2. **Trigger component**: One `logic_app_trigger` per trigger in the definition.
   - Properties: trigger type (HTTP, timer, Service Bus, etc.).
3. **Action components**: One `logic_app_action` per action.
   - Properties: action type, method, URI (for HTTP actions), queue/topic (for Service Bus).
4. **Edges**:
   - Workflow → each trigger (`triggers` edge)
   - Workflow → each action (`calls` edge)
   - Action → action (sequential flow based on `runAfter`)
5. **External references**: Inferred from HTTP action URIs, Service Bus connections, etc.

```python
# workers/parser/parsers/logic_app.py
class LogicAppParser(BaseParser):
    def parse(self, content: bytes, filename: str) -> ParseResult:
        data = json.loads(content)
        definition = data.get("definition", data)
        
        components = []
        edges = []
        externals = []
        
        # Create workflow component
        wf_name = Path(filename).stem
        wf = ParsedComponent(
            temp_id="wf_0",
            component_type="logic_app_workflow",
            name=wf_name,
            display_name=wf_name,
            properties={
                "triggerType": self._detect_trigger_type(definition),
                "actionCount": len(definition.get("actions", {})),
            }
        )
        components.append(wf)
        
        # Parse triggers
        for name, trigger in definition.get("triggers", {}).items():
            # ... create trigger component, edge from workflow
        
        # Parse actions
        for name, action in definition.get("actions", {}).items():
            # ... create action component, edges for runAfter
            # ... detect external references from HTTP URIs
        
        return ParseResult(components=components, edges=edges, external_references=externals)
```

### OpenAPI Spec Parser

Extracts:

1. **API definition component**: One `api_definition` per spec.
   - Properties: title, version, base URL, total operation count.
2. **Operation components**: One `api_operation` per path + method.
   - Properties: method, path, summary, parameters, request/response schemas.
3. **Schema components**: Key request/response schemas as `api_schema`.
4. **Edges**:
   - API definition → each operation (`has_operation` edge)
5. **External references**: Servers/basePath entries as external services.

Supports both OpenAPI v3 (`openapi: 3.x`) and Swagger v2 (`swagger: "2.0"`).

### APIM Policy XML Parser

Extracts:

1. **Policy components**: `apim_policy` for each policy section (inbound, outbound, backend, on-error).
   - Properties: policy names within the section (rate-limit, cors, set-header, etc.).
2. **Policy fragment components**: For `<include-fragment>` references.
3. **Edges**:
   - Policy → referenced backends (`depends_on` edge)
4. **External references**: Backend service URLs, named values.

```python
# workers/parser/parsers/apim_policy.py
import xml.etree.ElementTree as ET

class ApimPolicyParser(BaseParser):
    def parse(self, content: bytes, filename: str) -> ParseResult:
        root = ET.fromstring(content)
        components = []
        edges = []
        
        policy_name = Path(filename).stem
        policy = ParsedComponent(
            temp_id="pol_0",
            component_type="apim_policy",
            name=policy_name,
            display_name=policy_name,
            properties=self._extract_policy_names(root),
        )
        components.append(policy)
        
        # Extract backend URLs, named values, fragments
        # Create external references for backend URLs
        
        return ParseResult(components=components, edges=edges, external_references=externals)
```

### Parser Registry

```python
PARSER_REGISTRY: dict[str, BaseParser] = {
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

### Worker Handler

```python
class ParserHandler:
    async def handle(self, event_data: dict):
        artifact_id = event_data["artifactId"]
        tenant_id = event_data["tenantId"]
        
        # Transition to parsing
        await self.artifact_repo.update_status(tenant_id, artifact_id, "parsing")
        
        # Download raw artifact
        blob_path = event_data["blobPath"]
        content = await self.blob_service.download(blob_path)
        
        # Get parser for artifact type
        parser = get_parser(event_data["artifactType"])
        
        # Parse
        result = parser.parse(content, event_data.get("filename", ""))
        
        # Store parse result in Cosmos DB
        parse_result_doc = self._build_parse_result_doc(tenant_id, event_data, result)
        await self.parse_result_repo.create(parse_result_doc)
        
        # Update artifact status
        await self.artifact_repo.update_status(tenant_id, artifact_id, "parsed", parse_result={
            "componentCount": len(result.components),
            "edgeCount": len(result.edges),
            "parsedAt": result.parsed_at.isoformat(),
        })
        
        # Publish ArtifactParsed event
        await self.event_publisher.publish(...)
```

## Acceptance Criteria

- [ ] Parser worker consumes `ArtifactScanPassed` events
- [ ] Logic App JSON is parsed into workflow, trigger, and action components with correct edges
- [ ] OpenAPI spec (v2 and v3, JSON and YAML) is parsed into API definition and operation components
- [ ] APIM policy XML is parsed into policy components
- [ ] External references are inferred from HTTP URIs and backend URLs
- [ ] Parse results are stored in Cosmos DB `projects` container
- [ ] Artifact status transitions: `scan_passed` → `parsing` → `parsed`
- [ ] Parse failures transition to `parse_failed` with error details
- [ ] `ArtifactParsed` event is published after successful parsing
- [ ] `ArtifactParseFailed` event is published after failures
- [ ] Idempotency: re-processing an already-parsed artifact is a no-op
- [ ] Unit tests cover all three parsers with real fixture files
- [ ] Edge cases: empty workflows, specs with no operations, policies with no backends

## Definition of Done

- All three parsers produce correct components and edges from fixture files.
- Parse results are stored and queryable.
- The event pipeline flows: upload → scan → parse without manual intervention.
- The graph builder task (009) can consume parse results to build the graph.

## Risks / Gotchas

- **Logic App JSON structure**: Logic App Standard vs. Consumption may have different JSON structures. Focus on the `definition` property which is common.
- **OpenAPI v2 vs v3**: Significant structural differences (paths, basePath vs. servers). Test both.
- **APIM policy variations**: Policies can be nested and complex. Start with the most common patterns.
- **Large files**: Parser should handle files up to 10 MB without excessive memory usage.
- **Malformed input**: Parsers must fail gracefully with clear error messages, not crash the worker.

## Suggested Validation Steps

1. Upload a Logic App workflow JSON → verify parse result in Cosmos DB.
2. Upload an OpenAPI v3 JSON spec → verify API definition and operations are extracted.
3. Upload an OpenAPI v2 YAML spec → verify backwards compatibility.
4. Upload an APIM policy XML → verify policy components are extracted.
5. Upload a malformed JSON → verify `parse_failed` status with error details.
6. Run parser unit tests with fixture files.
7. Run the full pipeline: upload → scan-gate → parser → verify status transitions and events.
