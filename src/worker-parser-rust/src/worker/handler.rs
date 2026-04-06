//! Parser worker handler — downloads artifacts, parses them, stores results.
//!
//! Mirrors the Python `workers/parser/handler.py` ParserHandler.

use chrono::Utc;
use serde_json::{json, Value};
use ulid::Ulid;

use crate::azure::blob::BlobService;
use crate::azure::cosmos::CosmosService;
use crate::azure::event_grid::publisher::{build_cloud_event, EventGridPublisher};
use crate::event_types::{EVENT_ARTIFACT_PARSE_FAILED, EVENT_ARTIFACT_PARSED};
use crate::parsers;
use crate::worker::{WorkerError, WorkerHandler};

const DATABASE_NAME: &str = "integration-copilot";
const CONTAINER_NAME: &str = "projects";

/// Statuses that indicate the artifact has already progressed past the parse stage.
const POST_PARSE_STATUSES: &[&str] = &[
    "parsed",
    "parse_failed",
    "graph_building",
    "graph_built",
    "graph_failed",
];

/// Process `ArtifactScanPassed` events by parsing the raw artifact
/// and storing a structured parse result in Cosmos DB.
pub struct ParserHandler {
    blob: BlobService,
    cosmos: CosmosService,
    publisher: EventGridPublisher,
}

impl ParserHandler {
    pub fn new(
        blob: BlobService,
        cosmos: CosmosService,
        publisher: EventGridPublisher,
    ) -> Self {
        Self {
            blob,
            cosmos,
            publisher,
        }
    }

    /// Read the artifact document from Cosmos and return its status.
    async fn get_artifact_status(
        &self,
        tenant_id: &str,
        artifact_id: &str,
    ) -> Result<Option<String>, WorkerError> {
        let doc = self
            .cosmos
            .read_item(DATABASE_NAME, CONTAINER_NAME, artifact_id, tenant_id)
            .await
            .map_err(|e| WorkerError::Transient(format!("cosmos read failed: {e}")))?;

        Ok(doc
            .and_then(|d| d.get("status").and_then(Value::as_str).map(String::from)))
    }

    /// Transition artifact status via a patch (read-modify-write).
    async fn update_status(
        &self,
        tenant_id: &str,
        artifact_id: &str,
        new_status: &str,
    ) -> Result<(), WorkerError> {
        let doc = self
            .cosmos
            .read_item(DATABASE_NAME, CONTAINER_NAME, artifact_id, tenant_id)
            .await
            .map_err(|e| WorkerError::Transient(format!("cosmos read failed: {e}")))?;

        let mut doc = doc.ok_or_else(|| {
            WorkerError::Permanent(format!("Artifact {artifact_id} not found for tenant {tenant_id}"))
        })?;

        let etag = doc.get("_etag").and_then(Value::as_str).map(String::from);

        if let Some(obj) = doc.as_object_mut() {
            obj.insert("status".into(), json!(new_status));
            obj.insert("updatedAt".into(), json!(Utc::now().to_rfc3339()));
        }

        self.cosmos
            .replace_item(
                DATABASE_NAME,
                CONTAINER_NAME,
                artifact_id,
                tenant_id,
                &doc,
                etag.as_deref(),
            )
            .await
            .map_err(|e| WorkerError::Transient(format!("cosmos replace failed: {e}")))?;

        Ok(())
    }
}

#[async_trait::async_trait]
impl WorkerHandler for ParserHandler {
    async fn is_already_processed(&self, event_data: &Value) -> Result<bool, WorkerError> {
        let tenant_id = event_data
            .get("tenantId")
            .and_then(Value::as_str)
            .unwrap_or("");
        let artifact_id = event_data
            .get("artifactId")
            .and_then(Value::as_str)
            .unwrap_or("");

        let status = self.get_artifact_status(tenant_id, artifact_id).await?;
        Ok(status
            .map(|s| POST_PARSE_STATUSES.contains(&s.as_str()))
            .unwrap_or(false))
    }

    async fn handle(&self, event_data: &Value) -> Result<(), WorkerError> {
        let tenant_id = str_field(event_data, "tenantId")?;
        let project_id = str_field(event_data, "projectId")?;
        let artifact_id = str_field(event_data, "artifactId")?;

        // Fetch artifact record from Cosmos and transition scan_passed → parsing.
        // If the artifact is already in PARSING (retry after a transient failure),
        // skip the status transition and continue with the parse attempt.
        let artifact = self
            .cosmos
            .read_item(DATABASE_NAME, CONTAINER_NAME, artifact_id, tenant_id)
            .await
            .map_err(|e| WorkerError::Transient(format!("Failed to fetch artifact: {e}")))?
            .ok_or_else(|| {
                WorkerError::Permanent(format!(
                    "Artifact {artifact_id} not found for tenant {tenant_id}"
                ))
            })?;

        let current_status = artifact
            .get("status")
            .and_then(Value::as_str)
            .unwrap_or("");

        if current_status != "parsing" {
            self.update_status(tenant_id, artifact_id, "parsing")
                .await
                .map_err(|e| {
                    WorkerError::Transient(format!("Failed to transition to parsing: {e}"))
                })?;
        }

        // Use artifact record as source of truth for blob_path and artifact_type,
        // since upstream events may not include these fields.
        let blob_path = artifact
            .get("blobPath")
            .and_then(Value::as_str)
            .unwrap_or("");
        let artifact_type = artifact
            .get("artifactType")
            .and_then(Value::as_str)
            .unwrap_or("");

        if blob_path.is_empty() {
            return Err(WorkerError::Permanent(format!(
                "Artifact {artifact_id} has no blob path"
            )));
        }
        if artifact_type.is_empty() {
            return Err(WorkerError::Permanent(format!(
                "Artifact {artifact_id} has no artifact type"
            )));
        }

        // Download raw artifact from Blob Storage
        let content = self
            .blob
            .download_blob(blob_path)
            .await
            .map_err(|e| WorkerError::Transient(format!("Failed to download blob {blob_path}: {e}")))?;

        // Select parser
        let parser = parsers::get_parser(artifact_type).ok_or_else(|| {
            WorkerError::Permanent(format!("Unsupported artifact type: {artifact_type}"))
        })?;

        // Parse
        let filename = blob_path.rsplit('/').next().unwrap_or(blob_path);
        let result = parser
            .parse(&content, filename, artifact_id)
            .map_err(|e| WorkerError::Permanent(format!("Parse error for {filename}: {e}")))?;

        // Store parse result in Cosmos DB
        let parse_result_id = format!("pr_{}", Ulid::new());
        let doc = json!({
            "id": parse_result_id,
            "partitionKey": tenant_id,
            "type": "parse_result",
            "tenantId": tenant_id,
            "projectId": project_id,
            "artifactId": artifact_id,
            "artifactType": artifact_type,
            "components": result.components,
            "edges": result.edges,
            "externalReferences": result.external_references,
            "parsedAt": result.parsed_at.to_rfc3339(),
        });

        self.cosmos
            .create_item(DATABASE_NAME, CONTAINER_NAME, tenant_id, &doc)
            .await
            .map_err(|e| WorkerError::Transient(format!("Failed to store parse result: {e}")))?;

        // parsing → parsed
        self.update_status(tenant_id, artifact_id, "parsed")
            .await
            .map_err(|e| WorkerError::Transient(format!("Failed to transition to parsed: {e}")))?;

        // Publish ArtifactParsed event
        let event = build_cloud_event(
            EVENT_ARTIFACT_PARSED,
            "/integration-copilot/worker/artifact-parser",
            &format!("tenants/{tenant_id}/projects/{project_id}/artifacts/{artifact_id}"),
            json!({
                "tenantId": tenant_id,
                "projectId": project_id,
                "artifactId": artifact_id,
                "parseResultId": parse_result_id,
                "componentCount": result.components.len(),
                "edgeCount": result.edges.len(),
                "parsedAt": result.parsed_at.to_rfc3339(),
            }),
        );

        if let Err(e) = self.publisher.publish_event(&event).await {
            tracing::warn!(error = %e, "artifact_parsed_event_publish_failed");
        } else {
            tracing::info!(parse_result_id = %parse_result_id, "artifact_parsed_event_published");
        }

        Ok(())
    }

    async fn handle_failure(&self, event_data: &Value, error: &str) {
        let tenant_id = event_data
            .get("tenantId")
            .and_then(Value::as_str)
            .unwrap_or("unknown");
        let artifact_id = event_data
            .get("artifactId")
            .and_then(Value::as_str)
            .unwrap_or("unknown");
        let project_id = event_data
            .get("projectId")
            .and_then(Value::as_str)
            .unwrap_or("unknown");

        // Try to transition to parse_failed
        if let Ok(Some(status)) = self.get_artifact_status(tenant_id, artifact_id).await
            && !POST_PARSE_STATUSES.contains(&status.as_str())
            && let Err(e) = self
                .update_status(tenant_id, artifact_id, "parse_failed")
                .await
        {
            tracing::error!(error = %e, "update_status_to_parse_failed_error");
        }

        // Publish ArtifactParseFailed event
        let event = build_cloud_event(
            EVENT_ARTIFACT_PARSE_FAILED,
            "/integration-copilot/worker/artifact-parser",
            &format!("tenants/{tenant_id}/projects/{project_id}/artifacts/{artifact_id}"),
            json!({
                "tenantId": tenant_id,
                "projectId": project_id,
                "artifactId": artifact_id,
                "error": error,
            }),
        );

        if let Err(e) = self.publisher.publish_event(&event).await {
            tracing::error!(
                artifact_id = %artifact_id,
                error = %e,
                "handle_failure_event_publish_error"
            );
        }
    }
}

fn str_field<'a>(data: &'a Value, field: &str) -> Result<&'a str, WorkerError> {
    data.get(field)
        .and_then(Value::as_str)
        .ok_or_else(|| WorkerError::Permanent(format!("missing field: {field}")))
}
