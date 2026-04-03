//! Parser registry and trait definition.
//!
//! Mirrors the Python `parsers/__init__.py` registry that maps artifact types
//! to concrete parser implementations.

mod logic_app;

pub use logic_app::LogicAppParser;

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
    fn get_parser_returns_none_for_unknown() {
        assert!(get_parser("unknown_type").is_none());
    }
}
