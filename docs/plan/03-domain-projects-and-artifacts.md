# 03 — Domain: Projects and Artifacts

## Goals

- Define the project and artifact data models.
- Define the artifact upload lifecycle including malware scan gating.
- Define the artifact state machine with all valid transitions.
- Define supported artifact types and detection logic.
- Define blob storage path conventions.

## Scope

MVP: project CRUD, artifact upload/status tracking, malware scan gate stage, blob storage layout.

---

## Project Model

A **project** is a logical container for related integration artifacts. Each project belongs to one tenant.

### Project Entity

```json
{
  "id": "prj_01HQ...",
  "partitionKey": "tn_01HQXYZ...",
  "type": "project",
  "tenantId": "tn_01HQXYZ...",
  "name": "Order Processing Integration",
  "description": "Logic Apps and APIs for the order processing pipeline",
  "status": "active",
  "artifactCount": 7,
  "graphVersion": 3,
  "createdBy": "usr_01HQABC...",
  "createdAt": "2026-03-20T10:00:00Z",
  "updatedAt": "2026-03-25T14:30:00Z"
}
```

### Project Status

| Status | Description |
|--------|-------------|
| `active` | Normal operation |
| `archived` | Read-only; no new uploads or analyses |
| `deleted` | Soft-deleted; hidden from UI |

---

## Artifact Model

An **artifact** is a single uploaded file representing an integration component.

### Artifact Entity

```json
{
  "id": "art_01HQ...",
  "partitionKey": "tn_01HQXYZ...",
  "type": "artifact",
  "tenantId": "tn_01HQXYZ...",
  "projectId": "prj_01HQ...",
  "name": "order-processor.json",
  "artifactType": "logic_app_workflow",
  "status": "parsed",
  "fileSizeBytes": 24576,
  "blobPath": "tenants/tn_01HQXYZ/projects/prj_01HQ/artifacts/art_01HQ/order-processor.json",
  "contentHash": "sha256:abc123...",
  "parseResult": {
    "componentCount": 12,
    "edgeCount": 8,
    "parsedAt": "2026-03-25T14:32:00Z"
  },
  "error": null,
  "uploadedBy": "usr_01HQABC...",
  "createdAt": "2026-03-25T14:30:00Z",
  "updatedAt": "2026-03-25T14:32:00Z"
}
```

---

## Artifact Types

| Type Slug | Display Name | File Extension(s) | Detection Strategy |
|-----------|-------------|-------------------|-------------------|
| `logic_app_workflow` | Logic App Workflow | `.json` | JSON with `definition` property containing `triggers` and `actions` |
| `openapi_spec` | OpenAPI Specification | `.json`, `.yaml`, `.yml` | JSON/YAML with `openapi` or `swagger` top-level key |
| `apim_policy` | APIM Policy | `.xml` | XML with `<policies>` root element |
| `terraform` | Terraform (stretch) | `.tf` | HCL with `resource` or `data` blocks |
| `bicep` | Bicep (stretch) | `.bicep` | Bicep syntax |

### Detection Flow

```
Upload received
  → Check file extension
  → Read first N bytes for content-based detection
  → Match against known type signatures
  → If no match: status = "unsupported", error = { code: "UNSUPPORTED_TYPE", detail: "..." }
  → If match: set artifactType on metadata
```

For MVP, artifact type can also be explicitly provided by the uploader. Auto-detection is preferred but explicit type is accepted as an override.

---

## Artifact State Machine

```
                         ┌──────────────┐
                         │   uploading  │
                         └──────┬───────┘
                                │ upload complete
                         ┌──────▼───────┐
                         │   uploaded   │
                         └──────┬───────┘
                                │ submit for scan
                         ┌──────▼───────┐
                    ┌────│   scanning   │────┐
                    │    └──────────────┘    │
                    │ clean                  │ malware detected
             ┌──────▼───────┐        ┌──────▼───────┐
             │ scan_passed  │        │ scan_failed  │
             └──────┬───────┘        └──────────────┘
                    │ parse started
             ┌──────▼───────┐
        ┌────│   parsing    │────┐
        │    └──────────────┘    │
        │ success                │ failure
 ┌──────▼───────┐        ┌──────▼───────┐
 │    parsed    │        │ parse_failed │
 └──────┬───────┘        └──────────────┘
        │ graph build started
 ┌──────▼───────┐
 │graph_building│────┐
 └──────┬───────┘    │ failure
        │ success    │
 ┌──────▼───────┐  ┌─▼────────────┐
 │ graph_built  │  │graph_failed  │
 └──────────────┘  └──────────────┘
```

### Status Enum

```python
class ArtifactStatus(str, Enum):
    UPLOADING = "uploading"
    UPLOADED = "uploaded"
    SCANNING = "scanning"
    SCAN_PASSED = "scan_passed"
    SCAN_FAILED = "scan_failed"
    PARSING = "parsing"
    PARSED = "parsed"
    PARSE_FAILED = "parse_failed"
    GRAPH_BUILDING = "graph_building"
    GRAPH_BUILT = "graph_built"
    GRAPH_FAILED = "graph_failed"
    UNSUPPORTED = "unsupported"
```

### Valid Transitions

| From | To | Trigger |
|------|----|---------|
| `uploading` | `uploaded` | Upload complete |
| `uploaded` | `scanning` | Scan initiated |
| `scanning` | `scan_passed` | Defender scan clean |
| `scanning` | `scan_failed` | Malware detected |
| `scan_passed` | `parsing` | Parser worker picks up event |
| `parsing` | `parsed` | Parse successful |
| `parsing` | `parse_failed` | Parse error |
| `parsed` | `graph_building` | Graph builder picks up event |
| `graph_building` | `graph_built` | Graph update successful |
| `graph_building` | `graph_failed` | Graph build error |
| — | `unsupported` | Type detection failed |

### Terminal States

`scan_failed`, `parse_failed`, `graph_failed`, `unsupported`, `graph_built`

Users can retry failed artifacts by re-uploading (creates a new artifact, does not mutate the failed one).

---

## Defender for Storage Malware Scanning

### Placement in Flow

```
Upload → Blob Storage → Defender for Storage scans blob → Result event
  → If clean: transition to scan_passed, proceed to parsing
  → If malware: transition to scan_failed, notify user, do NOT parse
```

### MVP Implementation Note

- The architecture includes the malware scan gate as a required stage in the state machine.
- If Defender for Storage is not configured in the environment, the malware-scan-gate worker acts as a **passthrough**: it immediately transitions `uploaded` → `scan_passed`.
- This ensures the event flow and status transitions are always exercised, even in development environments without Defender.

---

## Blob Storage Path Conventions

### Path Format

```
tenants/{tenantId}/projects/{projectId}/artifacts/{artifactId}/{originalFilename}
```

### Examples

```
tenants/tn_01HQXYZ/projects/prj_01HQABC/artifacts/art_01HQDEF/order-processor.json
tenants/tn_01HQXYZ/projects/prj_01HQABC/artifacts/art_01HQGHI/catalog-api.yaml
tenants/tn_01HQXYZ/projects/prj_01HQABC/artifacts/art_01HQJKL/rate-limit-policy.xml
```

### Container

- Single blob container: `artifacts`
- Tenant isolation is at the path level, not the container level.
- The API backend accesses blobs using a managed identity with `Storage Blob Data Contributor` role.

---

## API-Visible Statuses and Error States

### Status Responses

The API returns artifact status as part of the artifact metadata. The frontend uses this to show progress.

```json
{
  "id": "art_01HQ...",
  "status": "parsing",
  "statusDetail": "Artifact is being parsed",
  "error": null
}
```

### Error Response

When an artifact is in a failed state, the `error` field contains details:

```json
{
  "id": "art_01HQ...",
  "status": "parse_failed",
  "statusDetail": "Parsing failed",
  "error": {
    "code": "PARSE_ERROR",
    "message": "Invalid Logic App workflow JSON: missing 'definition' property",
    "occurredAt": "2026-03-25T14:32:00Z"
  }
}
```

### Error Codes

| Code | Status | Description |
|------|--------|-------------|
| `UNSUPPORTED_TYPE` | `unsupported` | File type not recognized |
| `SCAN_MALWARE_DETECTED` | `scan_failed` | Malware found by Defender |
| `PARSE_ERROR` | `parse_failed` | Parser could not process the file |
| `PARSE_INVALID_SCHEMA` | `parse_failed` | File matched type but failed schema validation |
| `GRAPH_BUILD_ERROR` | `graph_failed` | Graph builder encountered an error |

---

## Cosmos DB Storage

Artifacts are stored in the `artifacts` container alongside project documents.

| Document Type | Partition Key | Query Pattern |
|---------------|--------------|---------------|
| `project` | `{tenantId}` | List projects for tenant |
| `artifact` | `{tenantId}` | List artifacts for tenant, filter by projectId |

### Why Single Partition Key on Tenant

- All queries are tenant-scoped.
- Listing artifacts for a project is a within-partition query with a filter on `projectId`.
- This avoids cross-partition queries for the most common access patterns.
- Cosmos DB serverless handles the partition sizing efficiently for MVP workloads.

---

## Decisions

| Decision | Chosen | Rationale |
|----------|--------|-----------|
| Artifact immutability | Artifacts are immutable after upload; re-upload creates new artifact | Simplifies state management; avoids versioning complexity |
| Malware scan gate | Always present in state machine; passthrough if Defender not configured | Ensures the flow is tested even without Defender |
| Blob path layout | `tenants/{tenantId}/projects/{projectId}/artifacts/{artifactId}/{filename}` | Tenant-scoped, unique, human-readable |
| Type detection | Content-based with extension hint | More reliable than extension alone; supports ambiguous cases |

## Assumptions

- Files are uploaded as multipart form data through the API, not directly to Blob Storage.
- Maximum file size for MVP is 10 MB (enforced at API layer).
- The API generates the artifact ID before uploading to blob storage.

## Open Questions

| # | Question |
|---|----------|
| 1 | Should we support ZIP uploads containing multiple artifacts? (Proposed: not for MVP) |
| 2 | Should artifact deletion cascade to blob deletion, or keep blobs for audit? |
