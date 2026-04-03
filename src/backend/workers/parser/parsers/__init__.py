"""Parser registry — maps artifact types to parser implementations."""

from __future__ import annotations

from workers.parser.parsers.apim_policy import ApimPolicyParser
from workers.parser.parsers.base import BaseParser
from workers.parser.parsers.logic_app import LogicAppParser
from workers.parser.parsers.openapi import OpenApiParser


class UnsupportedArtifactType(Exception):
    """Raised when no parser is registered for the given artifact type."""

    def __init__(self, artifact_type: str) -> None:
        super().__init__(f"No parser registered for artifact type: {artifact_type}")
        self.artifact_type = artifact_type


PARSER_REGISTRY: dict[str, BaseParser] = {
    "logic_app_workflow": LogicAppParser(),
    "openapi_spec": OpenApiParser(),
    "apim_policy": ApimPolicyParser(),
}


def get_parser(artifact_type: str) -> BaseParser:
    """Return the parser for the given artifact type.

    Raises :class:`UnsupportedArtifactType` if no parser is registered.
    """
    parser = PARSER_REGISTRY.get(artifact_type)
    if not parser:
        raise UnsupportedArtifactType(artifact_type)
    return parser
