//! Logic App workflow parser — extracts triggers, actions, and connections.
//!
//! Rust port of the Python `LogicAppParser` in `workers/parser/parsers/logic_app.py`.

use std::collections::HashMap;

use serde_json::Value;
use url::Url;

use crate::models::{ExternalReference, ParsedComponent, ParsedEdge, ParseResult};
use crate::parsers::{ParseError, Parser};

/// Parse Logic App workflow JSON definitions.
pub struct LogicAppParser;

impl Parser for LogicAppParser {
    fn parse(
        &self,
        content: &[u8],
        filename: &str,
        artifact_id: &str,
    ) -> Result<ParseResult, ParseError> {
        let data: Value = serde_json::from_slice(content).map_err(|e| {
            ParseError::Permanent(format!("Invalid JSON in {filename}: {e}"))
        })?;

        let definition = data.get("definition").unwrap_or(&data);
        let triggers = as_object(definition.get("triggers"));
        let actions = as_object(definition.get("actions"));

        let mut components = Vec::new();
        let mut edges = Vec::new();
        let mut external_refs: Vec<ExternalReference> = Vec::new();

        // Workflow component
        let workflow_id = "workflow_0";
        let trigger_type = triggers
            .values()
            .next()
            .and_then(|v| v.get("type"))
            .and_then(Value::as_str)
            .unwrap_or(if triggers.is_empty() { "none" } else { "unknown" });

        components.push(ParsedComponent {
            temp_id: workflow_id.into(),
            component_type: "logic_app_workflow".into(),
            name: filename.into(),
            display_name: filename.into(),
            properties: HashMap::from([
                ("triggerCount".into(), triggers.len().into()),
                ("actionCount".into(), actions.len().into()),
                ("triggerType".into(), trigger_type.into()),
            ]),
        });

        // Triggers
        for (idx, (trigger_name, trigger_def)) in triggers.iter().enumerate() {
            let trigger_id = format!("trigger_{idx}");
            let ttype = trigger_def
                .as_object()
                .and_then(|o| o.get("type"))
                .and_then(Value::as_str)
                .unwrap_or("unknown");

            components.push(ParsedComponent {
                temp_id: trigger_id.clone(),
                component_type: "logic_app_trigger".into(),
                name: trigger_name.clone(),
                display_name: trigger_name.clone(),
                properties: HashMap::from([("type".into(), ttype.into())]),
            });
            edges.push(ParsedEdge {
                source_temp_id: workflow_id.into(),
                target_temp_id: trigger_id,
                edge_type: "triggers".into(),
                properties: None,
            });
        }

        // Actions
        let mut action_ids: HashMap<String, String> = HashMap::new();
        for (idx, (action_name, action_def)) in actions.iter().enumerate() {
            let action_id = format!("action_{idx}");
            action_ids.insert(action_name.clone(), action_id.clone());

            let obj = action_def.as_object();
            let action_type = obj
                .and_then(|o| o.get("type"))
                .and_then(Value::as_str)
                .unwrap_or("unknown");

            let mut props: HashMap<String, Value> =
                HashMap::from([("type".into(), action_type.into())]);

            if action_type.eq_ignore_ascii_case("http") {
                if let Some(inputs) = obj.and_then(|o| o.get("inputs")).and_then(Value::as_object) {
                    if let Some(method) = inputs.get("method").and_then(Value::as_str) {
                        props.insert("method".into(), method.into());
                    }
                    if let Some(uri) = inputs.get("uri").and_then(Value::as_str) {
                        props.insert("uri".into(), uri.into());
                    }
                }
            }

            components.push(ParsedComponent {
                temp_id: action_id.clone(),
                component_type: "logic_app_action".into(),
                name: action_name.clone(),
                display_name: action_name.clone(),
                properties: props,
            });
            edges.push(ParsedEdge {
                source_temp_id: workflow_id.into(),
                target_temp_id: action_id,
                edge_type: "calls".into(),
                properties: None,
            });
        }

        // Action → action edges based on runAfter
        for (action_name, action_def) in &actions {
            let run_after = action_def
                .as_object()
                .and_then(|o| o.get("runAfter"))
                .and_then(Value::as_object);
            if let Some(deps) = run_after {
                for dep_name in deps.keys() {
                    if let (Some(source_id), Some(target_id)) =
                        (action_ids.get(dep_name), action_ids.get(action_name))
                    {
                        edges.push(ParsedEdge {
                            source_temp_id: source_id.clone(),
                            target_temp_id: target_id.clone(),
                            edge_type: "runs_after".into(),
                            properties: None,
                        });
                    }
                }
            }
        }

        // Infer external references from HTTP URIs
        let mut ext_idx: usize = 0;
        for (action_name, action_def) in &actions {
            let obj = match action_def.as_object() {
                Some(o) => o,
                None => continue,
            };
            let action_type = obj
                .get("type")
                .and_then(Value::as_str)
                .unwrap_or("");
            if action_type.eq_ignore_ascii_case("http") {
                if let Some(uri) = obj
                    .get("inputs")
                    .and_then(Value::as_object)
                    .and_then(|i| i.get("uri"))
                    .and_then(Value::as_str)
                {
                    let host = extract_host(uri);
                    if !host.is_empty() {
                        external_refs.push(ExternalReference {
                            temp_id: format!("ext_{ext_idx}"),
                            component_type: "external_service".into(),
                            name: host.clone(),
                            display_name: host,
                            inferred_from: format!("action:{action_name}:uri"),
                        });
                        ext_idx += 1;
                    }
                }
            }
        }

        // Infer external references from Service Bus connections
        let connections = data
            .pointer("/parameters/$connections/value")
            .and_then(Value::as_object);
        if let Some(conns) = connections {
            for (conn_name, conn_def) in conns {
                let obj = match conn_def.as_object() {
                    Some(o) => o,
                    None => continue,
                };
                let conn_id = obj
                    .get("connectionId")
                    .and_then(Value::as_str)
                    .unwrap_or("");
                if conn_id.to_lowercase().contains("servicebus")
                    || conn_name.to_lowercase().contains("servicebus")
                {
                    external_refs.push(ExternalReference {
                        temp_id: format!("ext_{ext_idx}"),
                        component_type: "external_service".into(),
                        name: format!("servicebus:{conn_name}"),
                        display_name: format!("Service Bus ({conn_name})"),
                        inferred_from: format!("connection:{conn_name}"),
                    });
                    ext_idx += 1;
                }
            }
        }

        let mut result = ParseResult::new(artifact_id, "logic_app_workflow");
        result.components = components;
        result.edges = edges;
        result.external_references = external_refs;
        Ok(result)
    }
}

/// Helper: treat `Option<&Value>` as an object, falling back to an empty map.
fn as_object(val: Option<&Value>) -> serde_json::Map<String, Value> {
    val.and_then(Value::as_object)
        .cloned()
        .unwrap_or_default()
}

/// Extract the hostname from a URI, returning empty string on failure.
fn extract_host(uri: &str) -> String {
    Url::parse(uri)
        .ok()
        .and_then(|u| u.host_str().map(String::from))
        .unwrap_or_default()
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_workflow() -> Vec<u8> {
        serde_json::to_vec(&serde_json::json!({
            "definition": {
                "triggers": {
                    "manual": {
                        "type": "Request",
                        "kind": "Http"
                    }
                },
                "actions": {
                    "Send_Email": {
                        "type": "ApiConnection",
                        "runAfter": {}
                    },
                    "Call_API": {
                        "type": "Http",
                        "inputs": {
                            "method": "GET",
                            "uri": "https://api.example.com/data"
                        },
                        "runAfter": {
                            "Send_Email": ["Succeeded"]
                        }
                    }
                }
            },
            "parameters": {
                "$connections": {
                    "value": {
                        "servicebus_conn": {
                            "connectionId": "/subscriptions/.../providers/Microsoft.Web/connections/servicebus"
                        }
                    }
                }
            }
        }))
        .unwrap()
    }

    #[test]
    fn parses_workflow_components() {
        let parser = LogicAppParser;
        let result = parser
            .parse(&sample_workflow(), "test.json", "art-1")
            .unwrap();

        // workflow + 1 trigger + 2 actions = 4 components
        assert_eq!(result.components.len(), 4);
        assert_eq!(result.artifact_id, "art-1");
        assert_eq!(result.artifact_type, "logic_app_workflow");

        let workflow = &result.components[0];
        assert_eq!(workflow.component_type, "logic_app_workflow");
        assert_eq!(workflow.properties["triggerCount"], 1);
        assert_eq!(workflow.properties["actionCount"], 2);
    }

    #[test]
    fn creates_trigger_edges() {
        let parser = LogicAppParser;
        let result = parser
            .parse(&sample_workflow(), "test.json", "a1")
            .unwrap();

        let trigger_edges: Vec<_> = result
            .edges
            .iter()
            .filter(|e| e.edge_type == "triggers")
            .collect();
        assert_eq!(trigger_edges.len(), 1);
        assert_eq!(trigger_edges[0].source_temp_id, "workflow_0");
    }

    #[test]
    fn creates_action_call_edges() {
        let parser = LogicAppParser;
        let result = parser
            .parse(&sample_workflow(), "test.json", "a1")
            .unwrap();

        let call_edges: Vec<_> = result
            .edges
            .iter()
            .filter(|e| e.edge_type == "calls")
            .collect();
        assert_eq!(call_edges.len(), 2);
    }

    #[test]
    fn creates_run_after_edges() {
        let parser = LogicAppParser;
        let result = parser
            .parse(&sample_workflow(), "test.json", "a1")
            .unwrap();

        let run_after: Vec<_> = result
            .edges
            .iter()
            .filter(|e| e.edge_type == "runs_after")
            .collect();
        assert_eq!(run_after.len(), 1);
    }

    #[test]
    fn extracts_http_external_references() {
        let parser = LogicAppParser;
        let result = parser
            .parse(&sample_workflow(), "test.json", "a1")
            .unwrap();

        let http_refs: Vec<_> = result
            .external_references
            .iter()
            .filter(|r| r.name == "api.example.com")
            .collect();
        assert_eq!(http_refs.len(), 1);
        assert_eq!(http_refs[0].inferred_from, "action:Call_API:uri");
    }

    #[test]
    fn extracts_servicebus_external_references() {
        let parser = LogicAppParser;
        let result = parser
            .parse(&sample_workflow(), "test.json", "a1")
            .unwrap();

        let sb_refs: Vec<_> = result
            .external_references
            .iter()
            .filter(|r| r.name.contains("servicebus"))
            .collect();
        assert_eq!(sb_refs.len(), 1);
        assert_eq!(sb_refs[0].display_name, "Service Bus (servicebus_conn)");
    }

    #[test]
    fn rejects_invalid_json() {
        let parser = LogicAppParser;
        let result = parser.parse(b"not json", "bad.json", "a1");
        assert!(result.is_err());
        let err = result.unwrap_err().to_string();
        assert!(err.contains("Invalid JSON"));
    }

    #[test]
    fn handles_empty_workflow() {
        let parser = LogicAppParser;
        let content = serde_json::to_vec(&serde_json::json!({"definition": {}})).unwrap();
        let result = parser.parse(&content, "empty.json", "a1").unwrap();
        assert_eq!(result.components.len(), 1); // just the workflow
        assert!(result.edges.is_empty());
        assert!(result.external_references.is_empty());
    }

    #[test]
    fn handles_workflow_without_definition_wrapper() {
        let parser = LogicAppParser;
        let content = serde_json::to_vec(&serde_json::json!({
            "triggers": {
                "recurrence": { "type": "Recurrence" }
            },
            "actions": {}
        }))
        .unwrap();
        let result = parser.parse(&content, "flat.json", "a1").unwrap();
        assert_eq!(result.components.len(), 2); // workflow + trigger
    }

    #[test]
    fn extract_host_works() {
        assert_eq!(extract_host("https://api.example.com/path"), "api.example.com");
        assert_eq!(extract_host("not a url"), "");
        assert_eq!(extract_host(""), "");
    }

    #[test]
    fn result_serializes_to_json() {
        let parser = LogicAppParser;
        let result = parser
            .parse(&sample_workflow(), "test.json", "art-1")
            .unwrap();

        let json = serde_json::to_string(&result).unwrap();
        assert!(json.contains("\"artifactId\":\"art-1\""));
        assert!(json.contains("\"componentType\":\"logic_app_workflow\""));
    }
}
