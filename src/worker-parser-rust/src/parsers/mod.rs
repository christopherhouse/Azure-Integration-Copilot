//! Parser registry and trait definition.
//!
//! Mirrors the Python `parsers/__init__.py` registry that maps artifact types
//! to concrete parser implementations.

mod apim_policy;
mod logic_app;
mod openapi;

pub use apim_policy::ApimPolicyParser;
pub use logic_app::LogicAppParser;
pub use openapi::OpenApiParser;

use crate::models::ParseResult;

/// Errors that can occur during parsing.
#[derive(Debug, thiserror::Error)]
pub enum ParseError {
    /// The content cannot be parsed and retrying will not help.
    #[error("permanent parse failure: {0}")]
    Permanent(String),
}

/// Trait that each artifact-type parser must implement.
pub trait Parser: Send + Sync {
    /// Parse raw artifact content and return structured components and edges.
    ///
    /// # Arguments
    /// * `content` – raw file bytes downloaded from Blob Storage
    /// * `filename` – original filename (used for display names and format detection)
    /// * `artifact_id` – unique identifier carried through to the `ParseResult`
    fn parse(
        &self,
        content: &[u8],
        filename: &str,
        artifact_id: &str,
    ) -> Result<ParseResult, ParseError>;
}

/// Return the parser for the given `artifact_type`, or `None` if unsupported.
pub fn get_parser(artifact_type: &str) -> Option<Box<dyn Parser>> {
    match artifact_type {
        "logic_app_workflow" => Some(Box::new(LogicAppParser)),
        "openapi_spec" => Some(Box::new(OpenApiParser)),
        "apim_policy" => Some(Box::new(ApimPolicyParser)),
        _ => None,
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn get_parser_returns_logic_app_parser() {
        assert!(get_parser("logic_app_workflow").is_some());
    }

    #[test]
    fn get_parser_returns_openapi_parser() {
        assert!(get_parser("openapi_spec").is_some());
    }

    #[test]
    fn get_parser_returns_apim_policy_parser() {
        assert!(get_parser("apim_policy").is_some());
    }

    #[test]
    fn get_parser_returns_none_for_unknown() {
        assert!(get_parser("unknown_type").is_none());
    }
}
