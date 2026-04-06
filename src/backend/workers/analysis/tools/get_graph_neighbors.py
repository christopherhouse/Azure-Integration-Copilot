"""Tool: get_graph_neighbors — returns neighbors for a component."""

from __future__ import annotations

import json

import structlog
from azure.ai.projects.models import FunctionTool

from domains.graph.repository import graph_repository

from .scoping import analysis_context

logger: structlog.stdlib.BoundLogger = structlog.get_logger(__name__)

TOOL_GET_GRAPH_NEIGHBORS = FunctionTool(
    name="get_graph_neighbors",
    description=(
        "Get the neighboring components connected to a given component by edges. "
        "Returns incoming, outgoing, or both directions."
    ),
    parameters={
        "type": "object",
        "properties": {
            "component_id": {
                "type": "string",
                "description": "The component ID to find neighbors for.",
            },
            "direction": {
                "type": "string",
                "enum": ["both", "incoming", "outgoing"],
                "description": "Edge direction filter. Defaults to 'both'.",
            },
        },
        "required": ["component_id"],
        "additionalProperties": False,
    },
    strict=False,
)


async def execute_get_graph_neighbors(
    component_id: str, direction: str = "both", **_kwargs: object
) -> str:
    """Execute get_graph_neighbors scoped to the current tenant/project."""
    ctx = analysis_context.get()
    pk = f"{ctx.tenant_id}:{ctx.project_id}"

    neighbors = await graph_repository.get_neighbors(pk, component_id, direction)

    result = []
    for n in neighbors:
        edge = n["edge"]
        comp = n["component"]
        result.append({
            "direction": n["direction"],
            "edge": {
                "id": edge.id,
                "edgeType": edge.edge_type,
                "sourceComponentId": edge.source_component_id,
                "targetComponentId": edge.target_component_id,
            },
            "component": {
                "id": comp.id,
                "name": comp.name,
                "displayName": comp.display_name,
                "componentType": comp.component_type,
            },
        })

    return json.dumps({"neighbors": result, "count": len(result)})
