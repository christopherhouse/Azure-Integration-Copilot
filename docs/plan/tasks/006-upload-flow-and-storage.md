# Task 006 — Upload Flow and Storage

## Title

Implement artifact file upload, Blob Storage integration, type detection, and ArtifactUploaded event publishing.

## Objective

Build the artifact upload endpoint that accepts multipart file uploads, stores raw files in Blob Storage, detects artifact types, computes content hashes, publishes ArtifactUploaded events, and provides a download endpoint. Also build the frontend upload UI.

## Why This Task Exists

Upload is the entry point for all value in the system. Without uploaded artifacts, there is nothing to parse, no graph to build, and nothing for the agent to analyze. This task connects the API to Blob Storage and Event Grid, starting the async processing pipeline.

## In Scope

- Multipart file upload endpoint (`POST /api/v1/projects/{projectId}/artifacts`)
- Blob Storage upload with tenant/project-scoped paths
- Artifact type detection (content-based + extension)
- Content hash computation (SHA-256)
- Artifact metadata creation in Cosmos DB (status: `uploading` → `uploaded`)
- ArtifactUploaded event publishing to Event Grid
- Artifact download endpoint (`GET /api/v1/projects/{projectId}/artifacts/{artifactId}/download`)
- Quota enforcement (file size, artifact count per project, total artifact count)
- Frontend: upload dropzone, upload progress, artifact list with status badges

## Out of Scope

- Malware scanning (scan-gate worker in task 007)
- Parsing (task 008)
- Graph building (task 009)
- Artifact re-upload or versioning
- ZIP file handling

## Dependencies

- **Task 005** (projects/artifacts domain): Artifact metadata model, state machine, Cosmos DB `projects` container.
- **Task 002** (API foundation): Blob Storage client wrapper, Event Grid publisher.
- **Task 004** (tenancy/auth): Quota enforcement middleware.

## Files/Directories Expected to Be Created or Modified

```
src/backend/
├── domains/
│   └── artifacts/
│       ├── router.py              # Updated: add upload and download endpoints
│       ├── service.py             # Updated: upload logic, type detection, event publishing
│       ├── models.py              # Updated: add upload-related models
│       ├── repository.py          # Updated: Blob Storage operations
│       └── type_detector.py       # New: artifact type detection logic
src/frontend/
├── src/
│   ├── app/(dashboard)/projects/[projectId]/artifacts/
│   │   └── page.tsx               # Artifact list + upload UI
│   ├── components/artifacts/
│   │   ├── artifact-list.tsx       # Artifact table with status badges
│   │   ├── artifact-upload.tsx     # Upload dropzone component
│   │   └── artifact-status-badge.tsx  # Status badge component
│   └── hooks/
│       └── use-artifacts.ts        # React Query hooks for artifacts
tests/backend/
├── test_artifact_upload.py
├── test_type_detection.py
└── test_artifact_download.py
```

## Implementation Notes

### Upload Endpoint

```python
@router.post("/api/v1/projects/{project_id}/artifacts", status_code=202)
async def upload_artifact(
    project_id: str,
    file: UploadFile,
    artifact_type: str | None = None,  # Optional override
    request: Request,
):
    tenant = request.state.tenant
    tier = request.state.tier
    
    # 1. Validate file size against tier limit
    if file.size > tier.limits.max_file_size_mb * 1024 * 1024:
        raise FileTooLargeError(file.size, tier.limits.max_file_size_mb)
    
    # 2. Generate artifact ID
    artifact_id = generate_id("art")
    
    # 3. Detect artifact type (or use provided override)
    detected_type = detect_artifact_type(file.filename, file)
    
    # 4. Create artifact metadata (status: uploading)
    artifact = create_artifact_metadata(tenant.id, project_id, artifact_id, file, detected_type)
    await artifact_repo.create(artifact)
    
    # 5. Upload to Blob Storage
    blob_path = f"tenants/{tenant.id}/projects/{project_id}/artifacts/{artifact_id}/{file.filename}"
    content_hash = await blob_service.upload(blob_path, file)
    
    # 6. Update artifact (status: uploaded, blob_path, content_hash)
    artifact = transition_and_update(artifact, ArtifactStatus.UPLOADED, blob_path=blob_path, content_hash=content_hash)
    await artifact_repo.update(artifact)
    
    # 7. Increment tenant usage counters
    await tenant_service.increment_artifact_count(tenant.id, project_id)
    
    # 8. Publish ArtifactUploaded event
    await event_publisher.publish(ArtifactUploadedEvent(
        tenant_id=tenant.id,
        project_id=project_id,
        artifact_id=artifact_id,
        artifact_type=detected_type,
        blob_path=blob_path,
        file_size_bytes=file.size,
        content_hash=content_hash,
    ))
    
    # 9. Return 202 with artifact metadata
    return ResponseEnvelope(data=artifact, meta=build_meta(request))
```

### Blob Storage Path Convention

```
tenants/{tenantId}/projects/{projectId}/artifacts/{artifactId}/{originalFilename}
```

Single container: `artifacts`. Tenant isolation at the path level.

### Type Detection

```python
# type_detector.py
def detect_artifact_type(filename: str, file: UploadFile) -> str:
    """Detect artifact type from filename and content."""
    ext = Path(filename).suffix.lower()
    content_head = file.file.read(8192)
    file.file.seek(0)  # Reset for upload
    
    # JSON-based detection
    if ext in ('.json', '.yaml', '.yml'):
        try:
            data = parse_json_or_yaml(content_head)
            if 'definition' in data and ('triggers' in data['definition'] or 'actions' in data['definition']):
                return 'logic_app_workflow'
            if 'openapi' in data or 'swagger' in data:
                return 'openapi_spec'
        except ParseError:
            pass
    
    # XML-based detection
    if ext == '.xml':
        if b'<policies>' in content_head:
            return 'apim_policy'
    
    # Stretch types
    if ext == '.tf':
        return 'terraform'
    if ext == '.bicep':
        return 'bicep'
    
    return 'unknown'
```

### Content Hash

```python
import hashlib

async def compute_hash(file: UploadFile) -> str:
    sha256 = hashlib.sha256()
    file.file.seek(0)
    while chunk := file.file.read(8192):
        sha256.update(chunk)
    file.file.seek(0)
    return f"sha256:{sha256.hexdigest()}"
```

### Download Endpoint

```python
@router.get("/api/v1/projects/{project_id}/artifacts/{artifact_id}/download")
async def download_artifact(project_id: str, artifact_id: str, request: Request):
    tenant = request.state.tenant
    artifact = await artifact_repo.get_by_id(tenant.id, artifact_id)
    if not artifact or artifact['projectId'] != project_id:
        raise NotFoundError("artifact", artifact_id)
    
    blob_stream = await blob_service.download(artifact['blobPath'])
    return StreamingResponse(blob_stream, media_type="application/octet-stream",
                           headers={"Content-Disposition": f"attachment; filename={artifact['name']}"})
```

### Frontend Upload UI

The artifact page includes:
1. **Upload dropzone**: Drag-and-drop area or file picker. Accepts `.json`, `.yaml`, `.yml`, `.xml` files.
2. **Upload progress**: Progress bar during upload.
3. **Artifact list**: Table showing name, type, status badge, file size, upload date.
4. **Status badges**: Color-coded badges per artifact status (see doc 08).

Use React Query mutations for upload and queries for listing with automatic refetch.

## Acceptance Criteria

- [ ] Upload a `.json` Logic App workflow → stored in Blob Storage with correct path
- [ ] Artifact metadata created in Cosmos DB with correct type detection
- [ ] Content hash (SHA-256) computed and stored
- [ ] ArtifactUploaded event published to Event Grid
- [ ] Artifact status transitions: `uploading` → `uploaded`
- [ ] Upload returns 202 with artifact metadata
- [ ] Quota enforcement: file size limit returns 413
- [ ] Quota enforcement: artifact count limit returns 429
- [ ] Download endpoint returns the raw file with correct filename
- [ ] Type detection correctly identifies Logic App, OpenAPI, and APIM policy
- [ ] Unknown file types are marked as `unsupported`
- [ ] Frontend: upload dropzone works with drag-and-drop and file picker
- [ ] Frontend: artifact list shows status badges that update
- [ ] Tests pass for upload, type detection, and download

## Definition of Done

- Files can be uploaded through the API and stored in Blob Storage.
- Artifact metadata is tracked in Cosmos DB with correct statuses.
- Events are published to trigger downstream processing.
- The frontend provides a functional upload experience.
- The processing pipeline (scan → parse → graph) can be triggered by uploading a file.

## Risks / Gotchas

- **Large file handling**: FastAPI's `UploadFile` streams data. Ensure Blob Storage upload also streams (not full read into memory).
- **Content-Type**: The upload endpoint accepts `multipart/form-data`, not JSON.
- **Type detection reset**: After reading content for detection, the file position must be reset before uploading to Blob.
- **Event Grid availability**: If Event Grid is not configured, the upload should still succeed (log a warning, skip event publishing).
- **CORS for file upload**: Ensure CORS allows `multipart/form-data` from the frontend origin.

## Suggested Validation Steps

1. Upload a Logic App JSON file: `curl -X POST -F "file=@workflow.json" http://localhost:8000/api/v1/projects/{id}/artifacts`
2. Verify blob exists in storage: check the Blob container `artifacts` for the expected path.
3. Verify artifact metadata in Cosmos DB: check the `projects` container for the artifact document.
4. Verify event published: check Event Grid Namespace for the ArtifactUploaded event.
5. Download the artifact: `GET /api/v1/projects/{id}/artifacts/{artifactId}/download` → verify file matches.
6. Upload an OpenAPI YAML → verify type detection is `openapi_spec`.
7. Upload an APIM policy XML → verify type detection is `apim_policy`.
8. Upload a .txt file → verify type is `unknown` and status is `unsupported`.
9. Test quota limits: upload beyond the limit → verify 429 response.
10. Test file size limit: upload a file > 10MB → verify 413 response.
