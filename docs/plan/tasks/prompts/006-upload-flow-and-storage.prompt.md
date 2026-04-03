# Prompt — Execute Task 006: Upload Flow and Storage

You are an expert Python backend engineer. Execute the following task to implement the artifact upload flow for Integrisight.ai.

## Context

Read these documents before starting:

- **Task spec**: `docs/plan/tasks/006-upload-flow-and-storage.md`
- **Projects and artifacts domain**: `docs/plan/03-domain-projects-and-artifacts.md`
- **Eventing and processing**: `docs/plan/05-domain-eventing-and-processing.md`
- **Frontend UX**: `docs/plan/08-frontend-and-ux.md`

**Prerequisites**: Tasks 002 (API foundation), 004 (tenancy/auth), and 005 (project/artifact domain) must be complete. Blob Storage client, artifact status state machine, and quota enforcement must be working.

## What You Must Do

Implement multipart artifact file upload, Blob Storage integration, artifact type detection, content hashing, ArtifactUploaded event publishing, download endpoint, and frontend upload UI.

### Step 1 — Artifact Type Detector

Create `src/backend/domains/artifacts/type_detector.py`:
- `detect_artifact_type(filename: str, file: UploadFile) -> str`
- Detection logic:
  - `.json`/`.yaml`/`.yml`: parse JSON/YAML, check for `definition` with `triggers`/`actions` → `logic_app_workflow`; check for `openapi`/`swagger` → `openapi_spec`
  - `.xml`: check for `<policies>` root element → `apim_policy`
  - `.tf` → `terraform` (stretch); `.bicep` → `bicep` (stretch)
  - Otherwise → `unknown`
- After reading content for detection, reset file position to 0.
- Add `pyyaml` to dependencies if not present.

### Step 2 — Upload Endpoint

Update `src/backend/domains/artifacts/router.py` — add:
- `POST /api/v1/projects/{project_id}/artifacts` — accepts `multipart/form-data` with `file: UploadFile` and optional `artifact_type: str`.
  1. Validate file size against `tier.limits.max_file_size_mb` (return 413 if exceeded).
  2. Generate artifact ID with `art_` prefix.
  3. Detect artifact type (or use override).
  4. Create artifact metadata in Cosmos DB (status: `uploading`).
  5. Upload file to Blob Storage at `tenants/{tenantId}/projects/{projectId}/artifacts/{artifactId}/{filename}`.
  6. Compute SHA-256 content hash.
  7. Update artifact metadata (status: `uploaded`, blob_path, content_hash).
  8. Increment tenant usage counters.
  9. Publish `ArtifactUploaded` CloudEvents event to Event Grid.
  10. Return 202 with artifact metadata.
- If type is `unknown`, set status to `unsupported` instead of `uploaded`.

### Step 3 — Download Endpoint

Add to artifact router:
- `GET /api/v1/projects/{project_id}/artifacts/{artifact_id}/download` — stream the raw file from Blob Storage with `Content-Disposition: attachment`.
- Validate artifact belongs to the requesting tenant and project.

### Step 4 — Content Hash

Create helper function:
```python
async def compute_hash(file: UploadFile) -> str:
    sha256 = hashlib.sha256()
    file.file.seek(0)
    while chunk := file.file.read(8192):
        sha256.update(chunk)
    file.file.seek(0)
    return f"sha256:{sha256.hexdigest()}"
```

### Step 5 — Event Publishing

Update `src/backend/shared/events.py` if needed to support publishing `ArtifactUploaded` events in CloudEvents v1.0 format:
```json
{
  "specversion": "1.0",
  "type": "com.integration-copilot.artifact.uploaded.v1",
  "source": "/integration-copilot/api",
  "subject": "tenants/{tenantId}/projects/{projectId}/artifacts/{artifactId}",
  "data": {
    "tenantId": "...",
    "projectId": "...",
    "artifactId": "...",
    "artifactType": "...",
    "blobPath": "...",
    "fileSizeBytes": 0,
    "contentHash": "sha256:..."
  }
}
```

### Step 6 — Frontend Upload UI

Create frontend components:
- `src/frontend/src/app/(dashboard)/projects/[projectId]/artifacts/page.tsx` — artifact list page with upload area.
- `src/frontend/src/components/artifacts/artifact-upload.tsx` — drag-and-drop upload dropzone accepting `.json`, `.yaml`, `.yml`, `.xml`.
- `src/frontend/src/components/artifacts/artifact-list.tsx` — table showing artifact name, type, status badge, file size, upload date.
- `src/frontend/src/components/artifacts/artifact-status-badge.tsx` — color-coded badges per status (green for `graph_built`, yellow for processing states, red for failures, gray for `unsupported`).
- `src/frontend/src/hooks/use-artifacts.ts` — React Query hooks for listing artifacts and upload mutation.

### Step 7 — Tests

Create tests:
- `tests/backend/test_artifact_upload.py` — test upload flow, metadata creation, blob storage.
- `tests/backend/test_type_detection.py` — test detection for Logic App, OpenAPI, APIM, and unknown types.
- `tests/backend/test_artifact_download.py` — test download streaming.

### Step 8 — Validation

1. Upload a Logic App JSON: `curl -X POST -F "file=@workflow.json" http://localhost:8000/api/v1/projects/{id}/artifacts` → 202 with type `logic_app_workflow`.
2. Verify blob at `tenants/{tenantId}/projects/{projectId}/artifacts/{artifactId}/workflow.json`.
3. Verify artifact metadata in Cosmos DB with status `uploaded`.
4. Verify `ArtifactUploaded` event published.
5. Download: `GET .../artifacts/{id}/download` → original file content.
6. Upload an OpenAPI YAML → type `openapi_spec`.
7. Upload APIM policy XML → type `apim_policy`.
8. Upload unknown .txt → type `unknown`, status `unsupported`.
9. Test file size limit and artifact count quota.
10. Frontend: upload via dropzone, verify artifact list with status badges.
11. `uv run pytest tests/backend/ -v` — all tests pass.

## Constraints

- Stream file data — do not read entire files into memory.
- Reset file position after type detection before uploading to Blob.
- If Event Grid is not configured, log a warning and skip event publishing (upload must still succeed).
- Ensure CORS allows `multipart/form-data` from the frontend origin.
- Do not implement malware scanning, parsing, or graph building.

## Done When

- Files upload through the API and land in Blob Storage with correct tenant-scoped paths.
- Artifact metadata tracks statuses correctly.
- Events are published to trigger downstream processing.
- The frontend provides a functional upload experience with status badges.
- All tests pass.
