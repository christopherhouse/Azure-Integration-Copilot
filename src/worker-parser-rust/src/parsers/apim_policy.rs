//! APIM policy XML parser — extracts policy sections and referenced backends.
//!
//! Rust port of the Python `ApimPolicyParser` in `workers/parser/parsers/apim_policy.py`.

use std::collections::HashMap;

use url::Url;

use crate::models::{ExternalReference, ParsedComponent, ParsedEdge, ParseResult};
use crate::parsers::{ParseError, Parser};

/// Recognised APIM policy section names.
const SECTIONS: &[&str] = &["inbound", "outbound", "backend", "on-error"];

/// Parse APIM policy XML documents.
pub struct ApimPolicyParser;

impl Parser for ApimPolicyParser {
    fn parse(
        &self,
        content: &[u8],
        filename: &str,
        artifact_id: &str,
    ) -> Result<ParseResult, ParseError> {
        let text = std::str::from_utf8(content).map_err(|e| {
            ParseError::Permanent(format!("Invalid UTF-8 in {filename}: {e}"))
        })?;

        let doc = roxmltree::Document::parse(text).map_err(|e| {
            ParseError::Permanent(format!("Invalid XML in {filename}: {e}"))
        })?;

        let root = doc.root_element();
        if root.tag_name().name() != "policies" {
            return Err(ParseError::Permanent(format!(
                "Expected <policies> root element in {filename}, got <{}>.",
                root.tag_name().name()
            )));
        }

        let mut components = Vec::new();
        let mut edges = Vec::new();
        let mut external_refs: Vec<ExternalReference> = Vec::new();

        // Collect section names for the root component
        let section_names: Vec<serde_json::Value> = root
            .children()
            .filter(|n| n.is_element() && SECTIONS.contains(&n.tag_name().name()))
            .map(|n| serde_json::Value::String(n.tag_name().name().to_owned()))
            .collect();

        let policy_root_id = "policy_0";
        components.push(ParsedComponent {
            temp_id: policy_root_id.into(),
            component_type: "apim_policy".into(),
            name: filename.into(),
            display_name: filename.into(),
            properties: HashMap::from([(
                "sections".into(),
                serde_json::Value::Array(section_names),
            )]),
        });

        let mut comp_idx: usize = 1;

        for section in root.children().filter(|n| n.is_element()) {
            let section_name = section.tag_name().name();
            if !SECTIONS.contains(&section_name) {
                continue;
            }

            let section_id = format!("policy_{comp_idx}");
            comp_idx += 1;

            let child_names: Vec<serde_json::Value> = section
                .children()
                .filter(|n| n.is_element())
                .map(|n| serde_json::Value::String(n.tag_name().name().to_owned()))
                .collect();
            let policy_count = child_names.len();

            components.push(ParsedComponent {
                temp_id: section_id.clone(),
                component_type: "apim_policy_section".into(),
                name: section_name.into(),
                display_name: format!("Section: {section_name}"),
                properties: HashMap::from([
                    ("section".into(), section_name.into()),
                    ("policyCount".into(), policy_count.into()),
                    (
                        "policies".into(),
                        serde_json::Value::Array(child_names),
                    ),
                ]),
            });
            edges.push(ParsedEdge {
                source_temp_id: policy_root_id.into(),
                target_temp_id: section_id,
                edge_type: "has_section".into(),
                properties: None,
            });

            // Inspect children for backend references
            for child in section.children().filter(|n| n.is_element()) {
                collect_backend_refs(child, &mut external_refs);
            }
        }

        let mut result = ParseResult::new(artifact_id, "apim_policy");
        result.components = components;
        result.edges = edges;
        result.external_references = external_refs;
        Ok(result)
    }
}

/// Recursively collect external references from backend URLs in XML elements.
fn collect_backend_refs(node: roxmltree::Node, refs: &mut Vec<ExternalReference>) {
    let tag = node.tag_name().name();

    // <set-backend-service base-url="...">
    if tag == "set-backend-service"
        && let Some(url) = node.attribute("base-url")
    {
        let host = extract_host(url);
        if !host.is_empty() {
            refs.push(ExternalReference {
                temp_id: format!("ext_{}", refs.len()),
                component_type: "external_service".into(),
                name: host.clone(),
                display_name: format!("Backend: {host}"),
                inferred_from: "set-backend-service:base-url".into(),
            });
        }
    }

    // <send-request> with <set-url>
    if tag == "send-request" {
        for child in node.children().filter(|n| n.is_element()) {
            if child.tag_name().name() == "set-url"
                && let Some(text) = child.text()
            {
                let host = extract_host(text.trim());
                if !host.is_empty() {
                    refs.push(ExternalReference {
                        temp_id: format!("ext_{}", refs.len()),
                        component_type: "external_service".into(),
                        name: host.clone(),
                        display_name: format!("Backend: {host}"),
                        inferred_from: "send-request:set-url".into(),
                    });
                }
            }
        }
    }

    // Recurse into children
    for child in node.children().filter(|n| n.is_element()) {
        collect_backend_refs(child, refs);
    }
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

    const SAMPLE_POLICY: &[u8] = br#"<policies>
    <inbound>
        <base />
        <rate-limit calls="100" renewal-period="60" />
        <set-backend-service base-url="https://backend.example.com/api" />
    </inbound>
    <backend>
        <base />
    </backend>
    <outbound>
        <base />
        <send-request mode="new" response-variable-name="resp">
            <set-url>https://external.service.io/callback</set-url>
            <set-method>POST</set-method>
        </send-request>
    </outbound>
    <on-error>
        <base />
    </on-error>
</policies>"#;

    #[test]
    fn parses_policy_sections() {
        let parser = ApimPolicyParser;
        let result = parser.parse(SAMPLE_POLICY, "policy.xml", "art-1").unwrap();

        // 1 root + 4 sections
        assert_eq!(result.components.len(), 5);
        assert_eq!(result.artifact_type, "apim_policy");

        let root = &result.components[0];
        assert_eq!(root.component_type, "apim_policy");

        let sections: Vec<_> = result
            .components
            .iter()
            .filter(|c| c.component_type == "apim_policy_section")
            .collect();
        assert_eq!(sections.len(), 4);

        let section_names: Vec<_> = sections.iter().map(|s| s.name.as_str()).collect();
        assert!(section_names.contains(&"inbound"));
        assert!(section_names.contains(&"backend"));
        assert!(section_names.contains(&"outbound"));
        assert!(section_names.contains(&"on-error"));
    }

    #[test]
    fn creates_section_edges() {
        let parser = ApimPolicyParser;
        let result = parser.parse(SAMPLE_POLICY, "policy.xml", "art-1").unwrap();

        let section_edges: Vec<_> = result
            .edges
            .iter()
            .filter(|e| e.edge_type == "has_section")
            .collect();
        assert_eq!(section_edges.len(), 4);
        assert!(section_edges.iter().all(|e| e.source_temp_id == "policy_0"));
    }

    #[test]
    fn extracts_backend_service_refs() {
        let parser = ApimPolicyParser;
        let result = parser.parse(SAMPLE_POLICY, "policy.xml", "art-1").unwrap();

        let backend_refs: Vec<_> = result
            .external_references
            .iter()
            .filter(|r| r.inferred_from == "set-backend-service:base-url")
            .collect();
        assert_eq!(backend_refs.len(), 1);
        assert_eq!(backend_refs[0].name, "backend.example.com");
    }

    #[test]
    fn extracts_send_request_refs() {
        let parser = ApimPolicyParser;
        let result = parser.parse(SAMPLE_POLICY, "policy.xml", "art-1").unwrap();

        let send_refs: Vec<_> = result
            .external_references
            .iter()
            .filter(|r| r.inferred_from == "send-request:set-url")
            .collect();
        assert_eq!(send_refs.len(), 1);
        assert_eq!(send_refs[0].name, "external.service.io");
    }

    #[test]
    fn counts_policies_per_section() {
        let parser = ApimPolicyParser;
        let result = parser.parse(SAMPLE_POLICY, "policy.xml", "art-1").unwrap();

        let inbound = result
            .components
            .iter()
            .find(|c| c.name == "inbound")
            .unwrap();
        // base, rate-limit, set-backend-service
        assert_eq!(inbound.properties["policyCount"], 3);
    }

    #[test]
    fn rejects_invalid_xml() {
        let parser = ApimPolicyParser;
        let err = parser.parse(b"<not valid", "bad.xml", "a1").unwrap_err();
        assert!(err.to_string().contains("Invalid XML"));
    }

    #[test]
    fn rejects_wrong_root_element() {
        let parser = ApimPolicyParser;
        let err = parser
            .parse(b"<configuration></configuration>", "wrong.xml", "a1")
            .unwrap_err();
        assert!(err.to_string().contains("Expected <policies> root element"));
    }

    #[test]
    fn handles_empty_policy() {
        let parser = ApimPolicyParser;
        let result = parser
            .parse(b"<policies></policies>", "empty.xml", "a1")
            .unwrap();
        assert_eq!(result.components.len(), 1); // just root
        assert!(result.edges.is_empty());
        assert!(result.external_references.is_empty());
    }

    #[test]
    fn result_serializes_to_json() {
        let parser = ApimPolicyParser;
        let result = parser.parse(SAMPLE_POLICY, "policy.xml", "art-1").unwrap();
        let json = serde_json::to_string(&result).unwrap();
        assert!(json.contains("\"artifactId\":\"art-1\""));
        assert!(json.contains("\"componentType\":\"apim_policy\""));
    }
}
