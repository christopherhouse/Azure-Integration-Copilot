//! Parse result models for artifact parsers.
//!
//! These mirror the Python Pydantic models in `workers/parser/models.py`,
//! using serde rename attributes to match the camelCase JSON contract.

use chrono::{DateTime, Utc};
use serde::{Deserialize, Serialize};
use std::collections::HashMap;

/// A component extracted from an artifact during parsing.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ParsedComponent {
    pub temp_id: String,
    pub component_type: String,
    pub name: String,
    pub display_name: String,
    #[serde(default)]
    pub properties: HashMap<String, serde_json::Value>,
}

/// An edge (relationship) between two components.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ParsedEdge {
    pub source_temp_id: String,
    pub target_temp_id: String,
    pub edge_type: String,
    #[serde(default, skip_serializing_if = "Option::is_none")]
    pub properties: Option<HashMap<String, serde_json::Value>>,
}

/// A reference to an external service inferred from artifact content.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ExternalReference {
    pub temp_id: String,
    #[serde(default = "default_component_type")]
    pub component_type: String,
    pub name: String,
    pub display_name: String,
    pub inferred_from: String,
}

fn default_component_type() -> String {
    "external_service".to_owned()
}

/// The complete result of parsing an artifact.
#[derive(Debug, Clone, Serialize, Deserialize, PartialEq)]
#[serde(rename_all = "camelCase")]
pub struct ParseResult {
    pub artifact_id: String,
    pub artifact_type: String,
    #[serde(default)]
    pub components: Vec<ParsedComponent>,
    #[serde(default)]
    pub edges: Vec<ParsedEdge>,
    #[serde(default)]
    pub external_references: Vec<ExternalReference>,
    pub parsed_at: DateTime<Utc>,
}

impl ParseResult {
    /// Create a new empty `ParseResult` with the current UTC timestamp.
    pub fn new(artifact_id: impl Into<String>, artifact_type: impl Into<String>) -> Self {
        Self {
            artifact_id: artifact_id.into(),
            artifact_type: artifact_type.into(),
            components: Vec::new(),
            edges: Vec::new(),
            external_references: Vec::new(),
            parsed_at: Utc::now(),
        }
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn parse_result_serializes_to_camel_case() {
        let result = ParseResult {
            artifact_id: "art-1".into(),
            artifact_type: "logic_app_workflow".into(),
            components: vec![ParsedComponent {
                temp_id: "wf_0".into(),
                component_type: "logic_app_workflow".into(),
                name: "my-workflow.json".into(),
                display_name: "my-workflow.json".into(),
                properties: HashMap::new(),
            }],
            edges: vec![],
            external_references: vec![],
            parsed_at: DateTime::parse_from_rfc3339("2026-01-01T00:00:00Z")
                .unwrap()
                .with_timezone(&Utc),
        };

        let json = serde_json::to_value(&result).unwrap();
        assert_eq!(json["artifactId"], "art-1");
        assert_eq!(json["artifactType"], "logic_app_workflow");
        assert_eq!(json["components"][0]["tempId"], "wf_0");
        assert_eq!(json["components"][0]["componentType"], "logic_app_workflow");
        assert_eq!(json["components"][0]["displayName"], "my-workflow.json");
    }

    #[test]
    fn parse_result_deserializes_from_camel_case() {
        let json = r#"{
            "artifactId": "art-2",
            "artifactType": "openapi_spec",
            "components": [],
            "edges": [],
            "externalReferences": [],
            "parsedAt": "2026-01-01T00:00:00Z"
        }"#;

        let result: ParseResult = serde_json::from_str(json).unwrap();
        assert_eq!(result.artifact_id, "art-2");
        assert_eq!(result.artifact_type, "openapi_spec");
        assert!(result.external_references.is_empty());
    }

    #[test]
    fn new_parse_result_has_utc_timestamp() {
        let result = ParseResult::new("a1", "logic_app_workflow");
        assert_eq!(result.artifact_id, "a1");
        assert!(result.components.is_empty());
        // parsed_at should be very close to now
        let diff = Utc::now() - result.parsed_at;
        assert!(diff.num_seconds() < 2);
    }

    #[test]
    fn external_reference_defaults_component_type() {
        let json = r#"{
            "tempId": "ext_0",
            "name": "sql-server",
            "displayName": "SQL Server",
            "inferredFrom": "connection_string"
        }"#;

        let ext: ExternalReference = serde_json::from_str(json).unwrap();
        assert_eq!(ext.component_type, "external_service");
    }

    #[test]
    fn parsed_edge_optional_properties() {
        let edge = ParsedEdge {
            source_temp_id: "a".into(),
            target_temp_id: "b".into(),
            edge_type: "triggers".into(),
            properties: None,
        };

        let json = serde_json::to_value(&edge).unwrap();
        assert!(json.get("properties").is_none());
    }
}
