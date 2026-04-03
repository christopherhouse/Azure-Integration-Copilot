//! OpenAPI / Swagger specification parser — extracts API definitions and operations.
//!
//! Rust port of the Python `OpenApiParser` in `workers/parser/parsers/openapi.py`.
//! Supports both JSON and YAML input, and handles OpenAPI v3 and Swagger v2 specs.

use std::collections::HashMap;

use serde_json::Value;

use crate::models::{ExternalReference, ParsedComponent, ParsedEdge, ParseResult};
use crate::parsers::{ParseError, Parser};

/// HTTP methods recognised in OpenAPI / Swagger path items.
const HTTP_METHODS: &[&str] = &[
    "get", "post", "put", "patch", "delete", "options", "head", "trace",
];

/// Parse OpenAPI v3 and Swagger v2 specifications (JSON and YAML).
pub struct OpenApiParser;

impl Parser for OpenApiParser {
    fn parse(
        &self,
        content: &[u8],
        filename: &str,
        artifact_id: &str,
    ) -> Result<ParseResult, ParseError> {
        let data = load_content(content, filename)?;

        let is_v3 = data.get("openapi").is_some();
        let is_v2 = data.get("swagger").is_some();
        if !is_v3 && !is_v2 {
            return Err(ParseError::Permanent(format!(
                "Unrecognised API spec format in {filename}: missing 'openapi' or 'swagger' key."
            )));
        }

        let mut components = Vec::new();
        let mut edges = Vec::new();
        let mut external_refs: Vec<ExternalReference> = Vec::new();

        let info = data.get("info").and_then(Value::as_object);
        let title = info
            .and_then(|i| i.get("title"))
            .and_then(Value::as_str)
            .unwrap_or(filename);
        let version = info
            .and_then(|i| i.get("version"))
            .and_then(Value::as_str)
            .unwrap_or("unknown");

        // Determine base URL
        let base_url = if is_v3 {
            data.get("servers")
                .and_then(Value::as_array)
                .and_then(|s| s.first())
                .and_then(|s| s.get("url"))
                .and_then(Value::as_str)
                .unwrap_or("")
                .to_owned()
        } else {
            let host = data
                .get("host")
                .and_then(Value::as_str)
                .unwrap_or("");
            let base_path = data
                .get("basePath")
                .and_then(Value::as_str)
                .unwrap_or("");
            let scheme = data
                .get("schemes")
                .and_then(Value::as_array)
                .and_then(|s| s.first())
                .and_then(Value::as_str)
                .unwrap_or("https");
            if host.is_empty() {
                String::new()
            } else {
                format!("{scheme}://{host}{base_path}")
            }
        };

        // Count operations
        let paths = data
            .get("paths")
            .and_then(Value::as_object)
            .cloned()
            .unwrap_or_default();
        let mut operation_count: usize = 0;
        for methods in paths.values() {
            if let Some(obj) = methods.as_object() {
                for method in obj.keys() {
                    if HTTP_METHODS.contains(&method.to_lowercase().as_str()) {
                        operation_count += 1;
                    }
                }
            }
        }

        let spec_version = data
            .get("openapi")
            .or_else(|| data.get("swagger"))
            .and_then(Value::as_str)
            .unwrap_or("unknown");

        // API definition component
        let api_id = "api_0";
        components.push(ParsedComponent {
            temp_id: api_id.into(),
            component_type: "api_definition".into(),
            name: title.into(),
            display_name: title.into(),
            properties: HashMap::from([
                ("title".into(), title.into()),
                ("version".into(), version.into()),
                ("baseUrl".into(), base_url.clone().into()),
                ("operationCount".into(), operation_count.into()),
                ("specVersion".into(), spec_version.into()),
            ]),
        });

        // Operations
        let mut op_idx: usize = 0;
        for (path, methods) in &paths {
            let obj = match methods.as_object() {
                Some(o) => o,
                None => continue,
            };
            for (method, op_def) in obj {
                if !HTTP_METHODS.contains(&method.to_lowercase().as_str()) {
                    continue;
                }
                let op_id = format!("op_{op_idx}");
                let summary = op_def
                    .as_object()
                    .and_then(|o| {
                        o.get("summary")
                            .or_else(|| o.get("operationId"))
                    })
                    .and_then(Value::as_str)
                    .unwrap_or("");

                let display = format!("{} {path}", method.to_uppercase());
                components.push(ParsedComponent {
                    temp_id: op_id.clone(),
                    component_type: "api_operation".into(),
                    name: display.clone(),
                    display_name: display,
                    properties: HashMap::from([
                        ("method".into(), method.to_uppercase().into()),
                        ("path".into(), Value::String(path.clone())),
                        ("summary".into(), summary.into()),
                    ]),
                });
                edges.push(ParsedEdge {
                    source_temp_id: api_id.into(),
                    target_temp_id: op_id,
                    edge_type: "has_operation".into(),
                    properties: None,
                });
                op_idx += 1;
            }
        }

        // External references from servers / host
        let mut ext_idx: usize = 0;
        if is_v3 {
            if let Some(servers) = data.get("servers").and_then(Value::as_array) {
                for server in servers {
                    if let Some(url) = server.get("url").and_then(Value::as_str)
                        && !url.is_empty()
                    {
                        external_refs.push(ExternalReference {
                            temp_id: format!("ext_{ext_idx}"),
                            component_type: "external_service".into(),
                            name: url.into(),
                            display_name: format!("Server: {url}"),
                            inferred_from: "servers".into(),
                        });
                        ext_idx += 1;
                    }
                }
            }
        } else if is_v2 {
            let host = data
                .get("host")
                .and_then(Value::as_str)
                .unwrap_or("");
            if !host.is_empty() {
                external_refs.push(ExternalReference {
                    temp_id: format!("ext_{ext_idx}"),
                    component_type: "external_service".into(),
                    name: host.into(),
                    display_name: format!("Host: {host}"),
                    inferred_from: "host".into(),
                });
                // suppress unused assignment warning in final branch
                let _ = ext_idx;
            }
        }

        let mut result = ParseResult::new(artifact_id, "openapi_spec");
        result.components = components;
        result.edges = edges;
        result.external_references = external_refs;
        Ok(result)
    }
}

/// Load JSON or YAML content, auto-detecting format from filename extension.
fn load_content(content: &[u8], filename: &str) -> Result<serde_json::Map<String, Value>, ParseError> {
    let text = std::str::from_utf8(content).map_err(|e| {
        ParseError::Permanent(format!("Invalid UTF-8 in {filename}: {e}"))
    })?;

    let lower = filename.to_lowercase();
    let value: Value = if lower.ends_with(".yaml") || lower.ends_with(".yml") {
        serde_yaml::from_str(text).map_err(|e| {
            ParseError::Permanent(format!("Invalid YAML in {filename}: {e}"))
        })?
    } else {
        serde_json::from_str(text).map_err(|e| {
            ParseError::Permanent(format!("Invalid JSON in {filename}: {e}"))
        })?
    };

    value.as_object().cloned().ok_or_else(|| {
        ParseError::Permanent(format!(
            "Expected a JSON/YAML object in {filename}, got {}.",
            match &value {
                Value::Array(_) => "array",
                Value::String(_) => "string",
                Value::Number(_) => "number",
                Value::Bool(_) => "bool",
                Value::Null => "null",
                Value::Object(_) => unreachable!(),
            }
        ))
    })
}

#[cfg(test)]
mod tests {
    use super::*;

    fn sample_openapi_v3_json() -> Vec<u8> {
        serde_json::to_vec(&serde_json::json!({
            "openapi": "3.0.3",
            "info": {
                "title": "Petstore API",
                "version": "1.0.0"
            },
            "servers": [
                { "url": "https://api.petstore.io/v1" }
            ],
            "paths": {
                "/pets": {
                    "get": {
                        "summary": "List all pets",
                        "operationId": "listPets"
                    },
                    "post": {
                        "summary": "Create a pet",
                        "operationId": "createPet"
                    }
                },
                "/pets/{petId}": {
                    "get": {
                        "summary": "Get a pet by ID",
                        "operationId": "getPet"
                    }
                }
            }
        }))
        .unwrap()
    }

    fn sample_swagger_v2_json() -> Vec<u8> {
        serde_json::to_vec(&serde_json::json!({
            "swagger": "2.0",
            "info": {
                "title": "Legacy API",
                "version": "0.9.0"
            },
            "host": "api.legacy.com",
            "basePath": "/v1",
            "schemes": ["https"],
            "paths": {
                "/users": {
                    "get": { "summary": "List users" }
                }
            }
        }))
        .unwrap()
    }

    #[test]
    fn parses_openapi_v3_components() {
        let parser = OpenApiParser;
        let result = parser
            .parse(&sample_openapi_v3_json(), "petstore.json", "art-1")
            .unwrap();

        // 1 api_definition + 3 operations
        assert_eq!(result.components.len(), 4);
        assert_eq!(result.artifact_type, "openapi_spec");

        let api = &result.components[0];
        assert_eq!(api.component_type, "api_definition");
        assert_eq!(api.properties["title"], "Petstore API");
        assert_eq!(api.properties["version"], "1.0.0");
        assert_eq!(api.properties["operationCount"], 3);
        assert_eq!(api.properties["specVersion"], "3.0.3");
    }

    #[test]
    fn creates_operation_edges() {
        let parser = OpenApiParser;
        let result = parser
            .parse(&sample_openapi_v3_json(), "petstore.json", "art-1")
            .unwrap();

        let op_edges: Vec<_> = result
            .edges
            .iter()
            .filter(|e| e.edge_type == "has_operation")
            .collect();
        assert_eq!(op_edges.len(), 3);
        assert!(op_edges.iter().all(|e| e.source_temp_id == "api_0"));
    }

    #[test]
    fn extracts_server_external_refs_v3() {
        let parser = OpenApiParser;
        let result = parser
            .parse(&sample_openapi_v3_json(), "petstore.json", "art-1")
            .unwrap();

        assert_eq!(result.external_references.len(), 1);
        assert_eq!(result.external_references[0].name, "https://api.petstore.io/v1");
        assert_eq!(result.external_references[0].inferred_from, "servers");
    }

    #[test]
    fn parses_swagger_v2() {
        let parser = OpenApiParser;
        let result = parser
            .parse(&sample_swagger_v2_json(), "legacy.json", "art-2")
            .unwrap();

        assert_eq!(result.components.len(), 2); // api + 1 operation
        let api = &result.components[0];
        assert_eq!(api.properties["baseUrl"], "https://api.legacy.com/v1");
        assert_eq!(api.properties["specVersion"], "2.0");
    }

    #[test]
    fn extracts_host_external_ref_v2() {
        let parser = OpenApiParser;
        let result = parser
            .parse(&sample_swagger_v2_json(), "legacy.json", "art-2")
            .unwrap();

        assert_eq!(result.external_references.len(), 1);
        assert_eq!(result.external_references[0].name, "api.legacy.com");
        assert_eq!(result.external_references[0].inferred_from, "host");
    }

    #[test]
    fn parses_yaml_openapi_spec() {
        let yaml = br#"
openapi: "3.0.3"
info:
  title: YAML API
  version: "2.0.0"
servers:
  - url: https://yaml-api.example.com
paths:
  /items:
    get:
      summary: List items
"#;
        let parser = OpenApiParser;
        let result = parser.parse(yaml, "spec.yaml", "art-3").unwrap();
        assert_eq!(result.components.len(), 2);
        assert_eq!(result.components[0].properties["title"], "YAML API");
    }

    #[test]
    fn rejects_unrecognised_format() {
        let data = serde_json::to_vec(&serde_json::json!({"something": "else"})).unwrap();
        let parser = OpenApiParser;
        let err = parser.parse(&data, "bad.json", "a1").unwrap_err();
        assert!(err.to_string().contains("Unrecognised API spec format"));
    }

    #[test]
    fn rejects_non_object_content() {
        let parser = OpenApiParser;
        let err = parser.parse(b"[1,2,3]", "arr.json", "a1").unwrap_err();
        assert!(err.to_string().contains("Expected a JSON/YAML object"));
    }

    #[test]
    fn handles_empty_paths() {
        let data = serde_json::to_vec(&serde_json::json!({
            "openapi": "3.0.0",
            "info": { "title": "Empty", "version": "1.0.0" },
            "paths": {}
        }))
        .unwrap();
        let parser = OpenApiParser;
        let result = parser.parse(&data, "empty.json", "a1").unwrap();
        assert_eq!(result.components.len(), 1); // just api_definition
        assert!(result.edges.is_empty());
    }

    #[test]
    fn operation_display_name_uses_uppercase_method() {
        let parser = OpenApiParser;
        let result = parser
            .parse(&sample_openapi_v3_json(), "petstore.json", "art-1")
            .unwrap();

        let ops: Vec<_> = result
            .components
            .iter()
            .filter(|c| c.component_type == "api_operation")
            .collect();
        assert!(ops.iter().all(|o| o.display_name.starts_with("GET") || o.display_name.starts_with("POST")));
    }
}
