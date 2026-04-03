//! Event type constants for Integrisight.ai CloudEvents.
//!
//! Mirrors the Python `shared/event_types.py` module.

pub const EVENT_ARTIFACT_UPLOADED: &str = "com.integration-copilot.artifact.uploaded.v1";
pub const EVENT_ARTIFACT_SCAN_PASSED: &str = "com.integration-copilot.artifact.scan-passed.v1";
pub const EVENT_ARTIFACT_SCAN_FAILED: &str = "com.integration-copilot.artifact.scan-failed.v1";
pub const EVENT_ARTIFACT_PARSED: &str = "com.integration-copilot.artifact.parsed.v1";
pub const EVENT_ARTIFACT_PARSE_FAILED: &str = "com.integration-copilot.artifact.parse-failed.v1";
pub const EVENT_GRAPH_UPDATED: &str = "com.integration-copilot.graph.updated.v1";
pub const EVENT_GRAPH_BUILD_FAILED: &str = "com.integration-copilot.graph.build-failed.v1";
pub const EVENT_ANALYSIS_REQUESTED: &str = "com.integration-copilot.analysis.requested.v1";
pub const EVENT_ANALYSIS_COMPLETED: &str = "com.integration-copilot.analysis.completed.v1";
pub const EVENT_ANALYSIS_FAILED: &str = "com.integration-copilot.analysis.failed.v1";
