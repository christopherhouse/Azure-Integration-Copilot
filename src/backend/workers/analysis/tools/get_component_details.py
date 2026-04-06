"""Tool: get_component_details — returns details for a specific component."""

from __future__ import annotations

import json

import structlog
from azure.ai.projects.models import FunctionTool

from domains.graph.repository import graph_repository

from .scoping import analysis_context

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

TOOL_GET_COMPONENT_DETAILS = FunctionTool(
    name="get_component_details",
    description=(
        "Get detailed information about a specific component in the dependency graph, "
        "including its type, properties, and tags."
    ),
    parameters={
        "type": "object",
        "properties": {
            "component_id": {
                "type": "string",
                "description": "The component ID to look up.",
            },
        },
        "required": ["component_id"],
        "additionalProperties": False,
    },
    strict=True,
)


async def execute_get_component_details(component_id: str, **_kwargs: object) -> str:
    """Execute get_component_details scoped to the current tenant/project."""
    ctx = analysis_context.get()
    pk = f"{ctx.tenant_id}:{ctx.project_id}"

    component = await graph_repository.get_component(pk, component_id)
    if component is None:
        return json.dumps({"error": f"Component '{component_id}' not found."})

    return json.dumps({
        "id": component.id,
        "name": component.name,
        "displayName": component.display_name,
        "componentType": component.component_type,
        "properties": component.properties,
        "tags": component.tags,
        "artifactId": component.artifact_id,
        "graphVersion": component.graph_version,
    })
