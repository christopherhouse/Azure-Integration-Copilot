"""Parse result models for artifact parsers."""

from __future__ import annotations

from datetime import UTC, datetime

from pydantic import BaseModel, Field


class ParsedComponent(BaseModel):
    """A component extracted from an artifact during parsing."""

    temp_id: str = Field(alias="tempId")
    component_type: str = Field(alias="componentType")
    name: str
    display_name: str = Field(alias="displayName")
    properties: dict = Field(default_factory=dict)

    model_config = {"populate_by_name": True}


class ParsedEdge(BaseModel):
    """An edge (relationship) between two components."""

    source_temp_id: str = Field(alias="sourceTempId")
    target_temp_id: str = Field(alias="targetTempId")
    edge_type: str = Field(alias="edgeType")
    properties: dict | None = None

    model_config = {"populate_by_name": True}


class ExternalReference(BaseModel):
    """A reference to an external service inferred from artifact content."""

    temp_id: str = Field(alias="tempId")
    component_type: str = Field(default="external_service", alias="componentType")
    name: str
    display_name: str = Field(alias="displayName")
    inferred_from: str = Field(alias="inferredFrom")

    model_config = {"populate_by_name": True}


class ParseResult(BaseModel):
    """The complete result of parsing an artifact."""

    artifact_id: str = Field(alias="artifactId")
    artifact_type: str = Field(alias="artifactType")
    components: list[ParsedComponent] = Field(default_factory=list)
    edges: list[ParsedEdge] = Field(default_factory=list)
    external_references: list[ExternalReference] = Field(default_factory=list, alias="externalReferences")
    parsed_at: datetime = Field(default_factory=lambda: datetime.now(UTC), alias="parsedAt")

    model_config = {"populate_by_name": True}
